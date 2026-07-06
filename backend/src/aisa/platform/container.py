from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from aisa.orchestration.application.ports import (
    JobQueue,
    RunEventSink,
    RunEventStream,
    RunRepository,
)
from aisa.orchestration.application.use_cases import CreateRun, ExecutePingRun, GetRun
from aisa.orchestration.infrastructure.redis_events import (
    PgRedisRunEventSink,
    PgRedisRunEventStream,
)
from aisa.orchestration.infrastructure.redis_queue import RedisStreamJobQueue
from aisa.orchestration.infrastructure.repository import SqlAlchemyRunRepository
from aisa.shared.clock import Clock, SystemClock
from aisa.shared.config import Settings
from aisa.shared.ids import new_id


@dataclass
class Container:
    """Composition root: wires ports to adapters. Constructor injection only."""

    settings: Settings
    engine: AsyncEngine | None
    redis: Redis | None
    clock: Clock
    run_repository: RunRepository
    job_queue: JobQueue
    run_event_sink: RunEventSink
    run_event_stream: RunEventStream
    create_run: CreateRun
    get_run: GetRun
    execute_ping_run: ExecutePingRun

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
        clock = SystemClock()

        run_repository = SqlAlchemyRunRepository(session_factory)
        job_queue = RedisStreamJobQueue(redis)
        run_event_sink = PgRedisRunEventSink(session_factory, redis, clock)
        run_event_stream = PgRedisRunEventStream(session_factory, redis)

        return cls(
            settings=settings,
            engine=engine,
            redis=redis,
            clock=clock,
            run_repository=run_repository,
            job_queue=job_queue,
            run_event_sink=run_event_sink,
            run_event_stream=run_event_stream,
            create_run=CreateRun(run_repository, job_queue, clock, new_id),
            get_run=GetRun(run_repository),
            execute_ping_run=ExecutePingRun(run_repository, run_event_sink, clock),
        )

    async def aclose(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
        if self.engine is not None:
            await self.engine.dispose()
