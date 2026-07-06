from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from aisa.shared.errors import DomainValidationError, InvalidStateError


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class Project:
    id: str
    workspace_id: str
    name: str
    description: str | None
    status: ProjectStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    settings: dict[str, object] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        project_id: str,
        workspace_id: str,
        name: str,
        description: str | None,
        settings: dict[str, object],
        created_by: str,
        now: datetime,
    ) -> Project:
        if not name.strip():
            raise DomainValidationError("Project name must not be empty")
        return cls(
            id=project_id,
            workspace_id=workspace_id,
            name=name.strip(),
            description=description,
            status=ProjectStatus.ACTIVE,
            settings=settings,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def rename(self, name: str, now: datetime) -> None:
        if not name.strip():
            raise DomainValidationError("Project name must not be empty")
        self.name = name.strip()
        self.updated_at = now

    def soft_delete(self, now: datetime) -> None:
        if self.is_deleted:
            raise InvalidStateError("Project is already deleted")
        self.deleted_at = now
        self.updated_at = now

    def restore(self, now: datetime) -> None:
        if not self.is_deleted:
            raise InvalidStateError("Project is not deleted")
        self.deleted_at = None
        self.updated_at = now
