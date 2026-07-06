from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from aisa.shared.errors import InvalidStateError


class ThreadRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class RequirementStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


@dataclass
class Thread:
    id: str
    workspace_id: str
    project_id: str
    created_at: datetime


@dataclass
class Message:
    id: str
    workspace_id: str
    thread_id: str
    role: ThreadRole
    content: dict[str, object]  # {"text": ..., "questions": [...]}
    run_id: str | None
    created_at: datetime

    @property
    def text(self) -> str:
        value = self.content.get("text", "")
        return value if isinstance(value, str) else ""


@dataclass
class RequirementDoc:
    id: str
    workspace_id: str
    project_id: str
    version: int
    status: RequirementStatus
    content: dict[str, object]
    created_by: str
    created_at: datetime

    def confirm(self) -> None:
        if self.status is RequirementStatus.CONFIRMED:
            raise InvalidStateError("Requirements are already confirmed")
        self.status = RequirementStatus.CONFIRMED
