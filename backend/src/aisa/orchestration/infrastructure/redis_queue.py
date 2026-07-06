import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import cast

import structlog
from redis.asyncio import Redis
from redis.exceptions import ResponseError

logger = structlog.get_logger(__name__)

JobHandler = Callable[[dict[str, str]], Awaitable[None]]


class RedisStreamJobQueue:
    """At-least-once job queue on Redis Streams with a consumer group.

    Failed jobs are re-enqueued with an incremented attempt counter; after
    `max_attempts` they land on the dead-letter stream for inspection.
    """

    def __init__(
        self,
        redis: Redis,
        stream: str = "aisa:jobs",
        group: str = "workers",
        max_attempts: int = 3,
    ) -> None:
        self._redis = redis
        self._stream = stream
        self._group = group
        self._max_attempts = max_attempts

    @property
    def dead_letter_stream(self) -> str:
        return f"{self._stream}:dead"

    async def enqueue(self, kind: str, payload: Mapping[str, str]) -> None:
        await self._enqueue(kind, dict(payload), attempt=1)

    async def _enqueue(self, kind: str, payload: dict[str, str], attempt: int) -> None:
        await self._redis.xadd(
            self._stream,
            {"kind": kind, "payload": json.dumps(payload), "attempt": str(attempt)},
        )

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume(
        self,
        handlers: Mapping[str, JobHandler],
        consumer: str,
        stop: asyncio.Event,
    ) -> None:
        await self.ensure_group()
        logger.info("worker.consuming", stream=self._stream, consumer=consumer)
        while not stop.is_set():
            raw = await self._redis.xreadgroup(
                self._group, consumer, {self._stream: ">"}, count=1, block=2000
            )
            if not raw:
                continue
            response = cast("list[tuple[str, list[tuple[str, dict[str, str]]]]]", raw)
            for _stream_name, messages in response:
                for message_id, fields in messages:
                    await self._process(message_id, fields, handlers)

    async def _process(
        self, message_id: str, fields: dict[str, str], handlers: Mapping[str, JobHandler]
    ) -> None:
        kind = fields.get("kind", "")
        attempt = int(fields.get("attempt", "1"))
        payload: dict[str, str] = json.loads(fields.get("payload", "{}"))
        try:
            handler = handlers.get(kind)
            if handler is None:
                raise LookupError(f"No handler registered for job kind '{kind}'")
            await handler(payload)
        except Exception:
            logger.exception("job.failed", kind=kind, attempt=attempt, message_id=message_id)
            if attempt < self._max_attempts:
                await self._enqueue(kind, payload, attempt=attempt + 1)
            else:
                await self._redis.xadd(
                    self.dead_letter_stream,
                    {"kind": kind, "payload": json.dumps(payload), "attempt": str(attempt)},
                )
                logger.error("job.dead_lettered", kind=kind, message_id=message_id)
        finally:
            await self._redis.xack(self._stream, self._group, message_id)
