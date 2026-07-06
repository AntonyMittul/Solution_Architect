from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aisa.identity.domain.models import Membership, Role, User, Workspace


class UserRepository(Protocol):
    async def add(self, user: User, password_hash: str | None) -> None: ...

    async def get(self, user_id: str) -> User:
        """Raises NotFoundError."""
        ...

    async def get_by_email(self, email: str) -> tuple[User, str | None] | None:
        """Returns (user, password_hash) or None."""
        ...

    async def save(self, user: User) -> None: ...


class WorkspaceRepository(Protocol):
    async def add(self, workspace: Workspace) -> None: ...

    async def get(self, workspace_id: str) -> Workspace:
        """Raises NotFoundError."""
        ...

    async def list_for_user(self, user_id: str) -> list[tuple[Workspace, Role]]: ...


class MembershipRepository(Protocol):
    async def add(self, membership: Membership) -> None: ...

    async def get(self, workspace_id: str, user_id: str) -> Membership | None: ...

    async def list_for_workspace(self, workspace_id: str) -> list[tuple[Membership, User]]: ...

    async def save(self, membership: Membership) -> None: ...

    async def remove(self, membership_id: str) -> None: ...


@dataclass
class RefreshTokenRecord:
    id: str
    user_id: str
    family_id: str
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None


class RefreshTokenRepository(Protocol):
    async def add(self, record: RefreshTokenRecord) -> None: ...

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None: ...

    async def mark_used(self, record_id: str, now: datetime) -> None: ...

    async def revoke_family(self, family_id: str, now: datetime) -> None: ...


class VerificationTokenRepository(Protocol):
    async def add(self, user_id: str, token_hash: str, expires_at: datetime) -> None: ...

    async def consume(self, token_hash: str, now: datetime) -> str | None:
        """Marks the token used and returns its user_id, or None if invalid/expired/used."""
        ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class AccessTokenCodec(Protocol):
    def issue(self, user_id: str) -> str: ...

    def verify(self, token: str) -> str:
        """Returns user_id. Raises UnauthorizedError on invalid/expired token."""
        ...


class EmailSender(Protocol):
    async def send_verification(self, email: str, token: str) -> None: ...
