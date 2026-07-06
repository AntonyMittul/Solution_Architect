import contextlib
import json
from collections.abc import AsyncIterator

from redis.asyncio import Redis
from sqlalchemy import select

from aisa.orchestration.application.ports import RunEvent
from aisa.orchestration.infrastructure.repository import SessionFactory
from aisa.orchestration.infrastructure.tables import AgentEventRow
from aisa.shared.clock import Clock

TERMINAL_EVENT_TYPES = frozenset({"run.completed", "run.failed", "run.cancelled"})


def _channel(run_id: str) -> str:
    return f"aisa:run:{run_id}:events"


def _seq_key(run_id: str) -> str:
    return f"aisa:run:{run_id}:seq"


class PgRedisRunEventSink:
    """Durable event log in Postgres + live fan-out via Redis pub/sub.

    The `agent_events` table is the source of truth and the SSE replay
    source; pub/sub only accelerates delivery to connected clients.
    """

    def __init__(self, session_factory: SessionFactory, redis: Redis, clock: Clock) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._clock = clock

    async def emit(self, run_id: str, event_type: str, payload: dict[str, object]) -> RunEvent:
        seq = int(await self._redis.incr(_seq_key(run_id)))
        async with self._session_factory() as session, session.begin():
            session.add(
                AgentEventRow(
                    run_id=run_id,
                    seq=seq,
                    type=event_type,
                    payload=payload,
                    created_at=self._clock.now(),
                )
            )
        event = RunEvent(run_id=run_id, seq=seq, type=event_type, payload=payload)
        await self._redis.publish(
            _channel(run_id),
            json.dumps({"seq": seq, "type": event_type, "payload": payload}),
        )
        return event


class PgRedisRunEventStream:
    """Replay persisted events after `after_seq`, then follow live pub/sub.

    Subscribes before replaying so no event can fall in the gap; duplicates
    are dropped by sequence number. Yields None as a heartbeat when idle.
    """

    def __init__(
        self, session_factory: SessionFactory, redis: Redis, heartbeat_seconds: float = 15.0
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._heartbeat_seconds = heartbeat_seconds

    async def stream(self, run_id: str, after_seq: int) -> AsyncIterator[RunEvent | None]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_channel(run_id))
        try:
            last_seq = after_seq
            for event in await self._replay(run_id, after_seq):
                last_seq = event.seq
                yield event
                if event.type in TERMINAL_EVENT_TYPES:
                    return
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=self._heartbeat_seconds
                )
                if message is None:
                    yield None  # heartbeat
                    continue
                data = json.loads(message["data"])
                if int(data["seq"]) <= last_seq:
                    continue  # already delivered during replay
                event = RunEvent(
                    run_id=run_id,
                    seq=int(data["seq"]),
                    type=str(data["type"]),
                    payload=dict(data["payload"]),
                )
                last_seq = event.seq
                yield event
                if event.type in TERMINAL_EVENT_TYPES:
                    return
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe(_channel(run_id))
                await pubsub.aclose()  # type: ignore[no-untyped-call]

    async def _replay(self, run_id: str, after_seq: int) -> list[RunEvent]:
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(AgentEventRow)
                .where(AgentEventRow.run_id == run_id, AgentEventRow.seq > after_seq)
                .order_by(AgentEventRow.seq)
            )
            return [
                RunEvent(run_id=row.run_id, seq=row.seq, type=row.type, payload=row.payload)
                for row in rows
            ]
