"""Walking-skeleton API test: web -> api -> queue -> worker -> events -> SSE,
with in-memory adapters standing in for Postgres/Redis. The same flow against
real infrastructure is exercised by `make smoke` / CI compose smoke test."""

from collections.abc import AsyncIterator

import httpx
import pytest

from aisa.orchestration.application.use_cases import CreateRun, ExecutePingRun, GetRun
from aisa.platform.app import create_app
from aisa.platform.container import Container
from aisa.shared.clock import SystemClock
from aisa.shared.config import Settings
from aisa.shared.ids import new_id
from tests.fakes import InlineJobQueue, InMemoryRunEvents, InMemoryRunRepository


@pytest.fixture
def container() -> Container:
    repo = InMemoryRunRepository()
    events = InMemoryRunEvents()
    clock = SystemClock()
    queue = InlineJobQueue()
    executor = ExecutePingRun(repo, events, clock)

    async def handle(payload: dict[str, str]) -> None:
        await executor.execute(payload["run_id"])

    queue.handlers["run.execute"] = handle
    return Container(
        settings=Settings(),
        engine=None,
        redis=None,
        clock=clock,
        run_repository=repo,
        job_queue=queue,
        run_event_sink=events,
        run_event_stream=events,
        create_run=CreateRun(repo, queue, clock, new_id),
        get_run=GetRun(repo),
        execute_ping_run=executor,
    )


@pytest.fixture
async def client(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(container))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_full_walking_skeleton_flow(client: httpx.AsyncClient) -> None:
    created = await client.post("/api/v1/runs", json={"kind": "ping"})
    assert created.status_code == 201
    run_id = created.json()["id"]

    fetched = await client.get(f"/api/v1/runs/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "completed"  # inline queue ran it synchronously

    async with client.stream("GET", f"/api/v1/runs/{run_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: run.status" in body
    assert body.count("event: agent.token") == 3
    assert "event: run.completed" in body


async def test_sse_reconnect_replays_only_after_last_event_id(
    client: httpx.AsyncClient,
) -> None:
    run_id = (await client.post("/api/v1/runs", json={"kind": "ping"})).json()["id"]

    async with client.stream(
        "GET", f"/api/v1/runs/{run_id}/events", headers={"Last-Event-ID": "3"}
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    assert "id: 1\n" not in body and "id: 3\n" not in body  # already delivered
    assert "id: 4\n" in body
    assert "event: run.completed" in body


async def test_unknown_run_returns_problem_json_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/runs/01FAKE0000000000000000FAKE")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["title"] == "Resource not found"
    assert problem["trace_id"]


async def test_invalid_kind_returns_problem_json_422(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/runs", json={"kind": "teleport"})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_health_live(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
