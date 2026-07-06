from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from aisa.shared.errors import InvalidStateError


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset(
        {RunStatus.NEEDS_INPUT, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
    ),
    RunStatus.NEEDS_INPUT: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
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
    workspace_id: str | None = None
    project_id: str | None = None
    triggered_by: str | None = None
    input: dict[str, object] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        run_id: str,
        kind: str,
        now: datetime,
        *,
        workspace_id: str | None = None,
        project_id: str | None = None,
        triggered_by: str | None = None,
        input: dict[str, object] | None = None,
    ) -> Run:
        return cls(
            id=run_id,
            kind=kind,
            status=RunStatus.QUEUED,
            created_at=now,
            workspace_id=workspace_id,
            project_id=project_id,
            triggered_by=triggered_by,
            input=input or {},
        )

    def start(self, now: datetime) -> None:
        self._transition_to(RunStatus.RUNNING)
        if self.started_at is None:
            self.started_at = now

    def await_input(self, now: datetime) -> None:
        self._transition_to(RunStatus.NEEDS_INPUT)

    def resume(self, now: datetime) -> None:
        """Resume a run that was paused for human input."""
        self._transition_to(RunStatus.RUNNING)

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

    @property
    def awaiting_input(self) -> bool:
        return self.status is RunStatus.NEEDS_INPUT

    def _transition_to(self, target: RunStatus) -> None:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStateError(f"Run {self.id}: cannot go from '{self.status}' to '{target}'")
        self.status = target
