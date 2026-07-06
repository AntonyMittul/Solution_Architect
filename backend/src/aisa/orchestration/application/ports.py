from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Protocol

from aisa.orchestration.domain.run import Run


class RunRepository(Protocol):
    async def add(self, run: Run) -> None: ...

    async def get(self, run_id: str) -> Run:
        """Raises NotFoundError if absent."""
        ...

    async def save(self, run: Run) -> None: ...


class JobQueue(Protocol):
    async def enqueue(self, kind: str, payload: Mapping[str, str]) -> None: ...


@dataclass(frozen=True)
class RunEvent:
    run_id: str
    seq: int
    type: str
    payload: dict[str, object]


class RunEventSink(Protocol):
    """Durably records a run event and fans it out to live subscribers."""

    async def emit(self, run_id: str, event_type: str, payload: dict[str, object]) -> RunEvent: ...


class RunEventStream(Protocol):
    """Ordered event stream for one run: replay after `after_seq`, then live.

    Yields None as a keepalive when no event arrived within the heartbeat
    interval; ends after a terminal run event.
    """

    def stream(self, run_id: str, after_seq: int) -> AsyncIterator[RunEvent | None]: ...
