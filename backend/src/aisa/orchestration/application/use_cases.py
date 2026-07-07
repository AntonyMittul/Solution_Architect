import asyncio
from collections.abc import Callable

import structlog

from aisa.orchestration.application.ports import JobQueue, RunEventSink, RunRepository
from aisa.orchestration.domain.run import Run
from aisa.shared.clock import Clock
from aisa.shared.errors import UnsupportedOperationError

logger = structlog.get_logger(__name__)


class CreateRun:
    """Creates a run of any kind and enqueues it. The worker dispatches by kind
    to the registered executor, so adding a run kind needs no change here."""

    def __init__(
        self,
        repository: RunRepository,
        queue: JobQueue,
        clock: Clock,
        id_factory: Callable[[], str],
        known_kinds: frozenset[str],
    ) -> None:
        self._repository = repository
        self._queue = queue
        self._clock = clock
        self._id_factory = id_factory
        self._known_kinds = known_kinds

    async def execute(
        self,
        kind: str,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
        triggered_by: str | None = None,
        input: dict[str, object] | None = None,
        token_budget: int = 0,
    ) -> Run:
        if kind not in self._known_kinds:
            raise UnsupportedOperationError(f"Unsupported run kind '{kind}'")
        run = Run.create(
            run_id=self._id_factory(),
            kind=kind,
            now=self._clock.now(),
            workspace_id=workspace_id,
            project_id=project_id,
            triggered_by=triggered_by,
            input=input,
            token_budget=token_budget,
        )
        await self._repository.add(run)
        await self._queue.enqueue("run.execute", {"run_id": run.id, "kind": run.kind})
        logger.info("run.created", run_id=run.id, kind=kind, workspace_id=workspace_id)
        return run


class EnqueueRunContinuation:
    """Re-enqueue an existing run (e.g. a needs_input run after the user
    answers). The executor decides whether that means start or resume."""

    def __init__(self, repository: RunRepository, queue: JobQueue) -> None:
        self._repository = repository
        self._queue = queue

    async def execute(self, run_id: str) -> None:
        run = await self._repository.get(run_id)
        await self._queue.enqueue("run.execute", {"run_id": run.id, "kind": run.kind})


class GetRun:
    def __init__(self, repository: RunRepository) -> None:
        self._repository = repository

    async def execute(self, run_id: str) -> Run:
        return await self._repository.get(run_id)


class ExecutePingRun:
    """Walking-skeleton executor: proves api -> queue -> worker -> events -> SSE.

    Replaced by the LangGraph orchestrator in M2; the surrounding contract
    (repository, event sink, terminal statuses) is the part that stays.
    """

    def __init__(self, repository: RunRepository, events: RunEventSink, clock: Clock) -> None:
        self._repository = repository
        self._events = events
        self._clock = clock

    async def execute(self, run_id: str) -> None:
        run = await self._repository.get(run_id)
        if run.is_terminal:
            logger.info("run.already_terminal", run_id=run_id, status=run.status)
            return  # redelivered job; idempotent no-op

        run.start(self._clock.now())
        await self._repository.save(run)
        await self._events.emit(run_id, "run.status", {"status": run.status.value})
        try:
            for i in range(1, 4):
                await asyncio.sleep(0.2)
                await self._events.emit(
                    run_id, "agent.token", {"agent": "walking_skeleton", "text": f"tick {i}"}
                )
            run.complete(self._clock.now())
            await self._repository.save(run)
            await self._events.emit(run_id, "run.completed", {"status": run.status.value})
            logger.info("run.completed", run_id=run_id)
        except Exception as exc:
            run.fail(self._clock.now(), error=str(exc))
            await self._repository.save(run)
            await self._events.emit(run_id, "run.failed", {"error": str(exc)})
            logger.exception("run.failed", run_id=run_id)
