from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from aisa.shared.authz import Role
from aisa.shared.errors import DomainValidationError

__all__ = ["Membership", "Role", "User", "Workspace", "WorkspaceKind", "make_slug"]

_SLUG_SANITIZE = re.compile(r"[^a-z0-9-]+")


def make_slug(text: str, unique_suffix: str) -> str:
    base = _SLUG_SANITIZE.sub("-", text.lower()).strip("-")[:32] or "workspace"
    return f"{base}-{unique_suffix.lower()[-6:]}"


class WorkspaceKind(StrEnum):
    PERSONAL = "personal"
    TEAM = "team"


@dataclass
class User:
    id: str
    email: str
    name: str
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def verify_email(self, now: datetime) -> None:
        self.email_verified = True
        self.updated_at = now


@dataclass
class Workspace:
    id: str
    slug: str
    name: str
    kind: WorkspaceKind
    plan: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    settings: dict[str, object] = field(default_factory=dict)

    @classmethod
    def create(
        cls, workspace_id: str, slug: str, name: str, kind: WorkspaceKind, now: datetime
    ) -> Workspace:
        if not name.strip():
            raise DomainValidationError("Workspace name must not be empty")
        return cls(
            id=workspace_id,
            slug=slug,
            name=name.strip(),
            kind=kind,
            plan="free",
            created_at=now,
            updated_at=now,
        )


@dataclass
class Membership:
    id: str
    workspace_id: str
    user_id: str
    role: Role
