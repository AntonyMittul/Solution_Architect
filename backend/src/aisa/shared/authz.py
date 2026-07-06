"""RBAC model: single source of truth for the doc-06 authorization matrix.

Lives in the shared kernel because every feature module authorizes against
it; the identity module owns *assigning* roles, not the model itself.
"""

from dataclasses import dataclass
from enum import StrEnum

from aisa.shared.errors import ForbiddenError


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Permission(StrEnum):
    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"  # create / edit / archive / soft-delete / restore
    RUN_TRIGGER = "run.trigger"
    MEMBER_MANAGE = "member.manage"
    WORKSPACE_MANAGE = "workspace.manage"  # settings, MCP servers, LLM config
    WORKSPACE_DELETE = "workspace.delete"  # billing & deletion — owner only


_VIEWER = frozenset({Permission.PROJECT_READ})
_MEMBER = _VIEWER | frozenset({Permission.PROJECT_WRITE, Permission.RUN_TRIGGER})
_ADMIN = _MEMBER | frozenset({Permission.MEMBER_MANAGE, Permission.WORKSPACE_MANAGE})
_OWNER = _ADMIN | frozenset({Permission.WORKSPACE_DELETE})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: _VIEWER,
    Role.MEMBER: _MEMBER,
    Role.ADMIN: _ADMIN,
    Role.OWNER: _OWNER,
}


@dataclass(frozen=True)
class Actor:
    """An authenticated user acting within one workspace."""

    user_id: str
    workspace_id: str
    role: Role
    email_verified: bool

    def can(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS[self.role]

    def require(self, permission: Permission) -> None:
        if not self.can(permission):
            raise ForbiddenError(f"Role '{self.role}' lacks permission '{permission}'")

    @property
    def audit_ref(self) -> str:
        return f"user:{self.user_id}"
