"""In-memory port implementations for fast, infrastructure-free tests."""

from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from aisa.identity.application.ports import RefreshTokenRecord
from aisa.orchestration.application.ports import RunEvent
from aisa.orchestration.domain.run import Run
from aisa.shared.errors import NotFoundError


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.current = start or datetime(2026, 7, 6, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.records: dict[str, RefreshTokenRecord] = {}  # keyed by record id

    async def add(self, record: RefreshTokenRecord) -> None:
        self.records[record.id] = replace(record)

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        for record in self.records.values():
            if record.token_hash == token_hash:
                return replace(record)
        return None

    async def mark_used(self, record_id: str, now: datetime) -> None:
        self.records[record_id].used_at = now

    async def revoke_family(self, family_id: str, now: datetime) -> None:
        for record in self.records.values():
            if record.family_id == family_id and record.revoked_at is None:
                record.revoked_at = now


TERMINAL_EVENT_TYPES = frozenset({"run.completed", "run.failed", "run.cancelled"})


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    async def add(self, run: Run) -> None:
        self._runs[run.id] = replace(run)

    async def get(self, run_id: str) -> Run:
        if run_id not in self._runs:
            raise NotFoundError(f"Run '{run_id}' not found")
        return replace(self._runs[run_id])

    async def save(self, run: Run) -> None:
        if run.id not in self._runs:
            raise NotFoundError(f"Run '{run.id}' not found")
        self._runs[run.id] = replace(run)

    async def latest_for_project(self, project_id: str, kind: str) -> Run | None:
        matches = [r for r in self._runs.values() if r.project_id == project_id and r.kind == kind]
        if not matches:
            return None
        return replace(max(matches, key=lambda r: r.created_at))


class RecordingJobQueue:
    """Records enqueued jobs without executing them."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict[str, str]]] = []

    async def enqueue(self, kind: str, payload: Mapping[str, str]) -> None:
        self.jobs.append((kind, dict(payload)))


class InlineJobQueue:
    """Executes the handler immediately on enqueue — collapses api->worker for tests."""

    def __init__(self) -> None:
        self.handlers: dict[str, Callable[[dict[str, str]], Awaitable[None]]] = {}

    async def enqueue(self, kind: str, payload: Mapping[str, str]) -> None:
        await self.handlers[kind](dict(payload))


class InMemoryRunEvents:
    """Implements both RunEventSink and RunEventStream over a plain list."""

    def __init__(self) -> None:
        self._events: dict[str, list[RunEvent]] = defaultdict(list)

    async def emit(self, run_id: str, event_type: str, payload: dict[str, object]) -> RunEvent:
        seq = len(self._events[run_id]) + 1
        event = RunEvent(run_id=run_id, seq=seq, type=event_type, payload=payload)
        self._events[run_id].append(event)
        return event

    async def stream(self, run_id: str, after_seq: int) -> AsyncIterator[RunEvent | None]:
        for event in list(self._events[run_id]):
            if event.seq <= after_seq:
                continue
            yield event
            if event.type in TERMINAL_EVENT_TYPES:
                return
