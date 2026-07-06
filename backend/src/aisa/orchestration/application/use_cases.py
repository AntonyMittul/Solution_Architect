import asyncio
from collections.abc import Callable

import structlog

from aisa.orchestration.application.ports import JobQueue, RunEventSink, RunRepository
from aisa.orchestration.domain.run import Run
from aisa.shared.clock import Clock
from aisa.shared.errors import UnsupportedOperationError

logger = structlog.get_logger(__name__)

SUPPORTED_KINDS = frozenset({"ping"})


class CreateRun:
    def __init__(
        self,
        repository: RunRepository,
        queue: JobQueue,
        clock: Clock,
        id_factory: Callable[[], str],
    ) -> None:
        self._repository = repository
        self._queue = queue
        self._clock = clock
        self._id_factory = id_factory

    async def execute(self, kind: str) -> Run:
        if kind not in SUPPORTED_KINDS:
            raise UnsupportedOperationError(f"Unsupported run kind '{kind}'")
        run = Run.create(run_id=self._id_factory(), kind=kind, now=self._clock.now())
        await self._repository.add(run)
        await self._queue.enqueue("run.execute", {"run_id": run.id})
        logger.info("run.created", run_id=run.id, kind=kind)
        return run


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
