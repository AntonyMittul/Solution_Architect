import asyncio
import contextlib
import os
import signal
import socket

import structlog

from aisa.orchestration.infrastructure.redis_queue import RedisStreamJobQueue
from aisa.platform.container import Container
from aisa.shared.config import Settings
from aisa.shared.logging import configure_logging
from aisa.shared.telemetry import configure_metrics, configure_tracing, get_tracer

logger = structlog.get_logger(__name__)
_tracer = get_tracer("aisa.worker")


async def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level, json_logs=not settings.is_dev)
    configure_tracing(settings, "aisa-worker")
    configure_metrics(settings, "aisa-worker")
    container = Container.build(settings)
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # not supported on Windows
            loop.add_signal_handler(sig, stop.set)

    consumer_name = f"{socket.gethostname()}:{os.getpid()}"
    queue = container.job_queue
    assert isinstance(queue, RedisStreamJobQueue)

    async def handle_run_execute(payload: dict[str, str]) -> None:
        # Dispatch by run kind to the registered executor (ping, intake, ...).
        executor = container.run_executors.get(payload["kind"])
        if executor is None:
            logger.error("worker.no_executor", kind=payload.get("kind"))
            return
        with _tracer.start_as_current_span(
            "run.execute",
            attributes={"aisa.run_kind": payload["kind"], "aisa.run_id": payload["run_id"]},
        ):
            await executor.execute(payload["run_id"])

    logger.info("worker.starting", consumer=consumer_name)
    try:
        await queue.consume({"run.execute": handle_run_execute}, consumer_name, stop)
    finally:
        await container.aclose()
        logger.info("worker.stopped")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
