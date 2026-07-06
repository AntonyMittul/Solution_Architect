import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from aisa.orchestration.application.ports import RunEvent, RunEventStream
from aisa.orchestration.application.use_cases import CreateRun, GetRun
from aisa.orchestration.domain.run import Run

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    kind: Literal["ping"]


class RunResponse(BaseModel):
    id: str
    kind: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None

    @classmethod
    def from_domain(cls, run: Run) -> "RunResponse":
        return cls(
            id=run.id,
            kind=run.kind,
            status=run.status.value,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
        )


def _create_run(request: Request) -> CreateRun:
    use_case: CreateRun = request.app.state.container.create_run
    return use_case


def _get_run(request: Request) -> GetRun:
    use_case: GetRun = request.app.state.container.get_run
    return use_case


def _event_stream(request: Request) -> RunEventStream:
    stream: RunEventStream = request.app.state.container.run_event_stream
    return stream


@router.post("", status_code=201)
async def create_run(
    body: CreateRunRequest, use_case: Annotated[CreateRun, Depends(_create_run)]
) -> RunResponse:
    run = await use_case.execute(kind=body.kind)
    return RunResponse.from_domain(run)


@router.get("/{run_id}")
async def get_run(run_id: str, use_case: Annotated[GetRun, Depends(_get_run)]) -> RunResponse:
    run = await use_case.execute(run_id)
    return RunResponse.from_domain(run)


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str,
    get_run_uc: Annotated[GetRun, Depends(_get_run)],
    events: Annotated[RunEventStream, Depends(_event_stream)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    after: int = 0,
) -> StreamingResponse:
    """SSE stream of run events. Reconnect resumes via Last-Event-ID (or ?after=seq)."""
    await get_run_uc.execute(run_id)  # 404 before the stream starts, not inside it
    after_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else after

    async def body() -> AsyncIterator[str]:
        async for event in events.stream(run_id, after_seq):
            yield _format_sse(event)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _format_sse(event: RunEvent | None) -> str:
    if event is None:
        return ": heartbeat\n\n"
    data = json.dumps({"run_id": event.run_id, "payload": event.payload, "v": 1})
    return f"id: {event.seq}\nevent: {event.type}\ndata: {data}\n\n"
