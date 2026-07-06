from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from aisa.shared.errors import InvalidStateError


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}

TERMINAL_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})


@dataclass
class Run:
    id: str
    kind: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    @classmethod
    def create(cls, run_id: str, kind: str, now: datetime) -> Run:
        return cls(id=run_id, kind=kind, status=RunStatus.QUEUED, created_at=now)

    def start(self, now: datetime) -> None:
        self._transition_to(RunStatus.RUNNING)
        self.started_at = now

    def complete(self, now: datetime) -> None:
        self._transition_to(RunStatus.COMPLETED)
        self.finished_at = now

    def fail(self, now: datetime, error: str) -> None:
        self._transition_to(RunStatus.FAILED)
        self.finished_at = now
        self.error = error

    def cancel(self, now: datetime) -> None:
        self._transition_to(RunStatus.CANCELLED)
        self.finished_at = now

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def _transition_to(self, target: RunStatus) -> None:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStateError(f"Run {self.id}: cannot go from '{self.status}' to '{target}'")
        self.status = target
