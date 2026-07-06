from datetime import datetime

from sqlalchemy import select, update

from aisa.identity.application.ports import RefreshTokenRecord
from aisa.identity.domain.models import Membership, Role, User, Workspace, WorkspaceKind
from aisa.identity.infrastructure.tables import (
    EmailVerificationTokenRow,
    MembershipRow,
    RefreshTokenRow,
    UserRow,
    WorkspaceRow,
)
from aisa.shared.db import SessionFactory
from aisa.shared.errors import NotFoundError


class SqlUserRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, user: User, password_hash: str | None) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                UserRow(
                    id=user.id,
                    email=user.email,
                    password_hash=password_hash,
                    name=user.name,
                    email_verified=user.email_verified,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    deleted_at=user.deleted_at,
                )
            )

    async def get(self, user_id: str) -> User:
        async with self._session_factory() as session:
            row = await session.get(UserRow, user_id)
            if row is None or row.deleted_at is not None:
                raise NotFoundError(f"User '{user_id}' not found")
            return _user_to_domain(row)

    async def get_by_email(self, email: str) -> tuple[User, str | None] | None:
        async with self._session_factory() as session:
            row = await session.scalar(select(UserRow).where(UserRow.email == email))
            if row is None or row.deleted_at is not None:
                return None
            return _user_to_domain(row), row.password_hash

    async def save(self, user: User) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(UserRow, user.id)
            if row is None:
                raise NotFoundError(f"User '{user.id}' not found")
            row.name = user.name
            row.email_verified = user.email_verified
            row.updated_at = user.updated_at
            row.deleted_at = user.deleted_at


class SqlWorkspaceRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, workspace: Workspace) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                WorkspaceRow(
                    id=workspace.id,
                    slug=workspace.slug,
                    name=workspace.name,
                    kind=workspace.kind.value,
                    plan=workspace.plan,
                    settings=dict(workspace.settings),
                    created_at=workspace.created_at,
                    updated_at=workspace.updated_at,
                    deleted_at=workspace.deleted_at,
                )
            )

    async def get(self, workspace_id: str) -> Workspace:
        async with self._session_factory() as session:
            row = await session.get(WorkspaceRow, workspace_id)
            if row is None or row.deleted_at is not None:
                raise NotFoundError(f"Workspace '{workspace_id}' not found")
            return _workspace_to_domain(row)

    async def list_for_user(self, user_id: str) -> list[tuple[Workspace, Role]]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(WorkspaceRow, MembershipRow.role)
                .join(MembershipRow, MembershipRow.workspace_id == WorkspaceRow.id)
                .where(MembershipRow.user_id == user_id, WorkspaceRow.deleted_at.is_(None))
                .order_by(WorkspaceRow.created_at)
            )
            return [(_workspace_to_domain(ws), Role(role)) for ws, role in rows.all()]


class SqlMembershipRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, membership: Membership) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                MembershipRow(
                    id=membership.id,
                    workspace_id=membership.workspace_id,
                    user_id=membership.user_id,
                    role=membership.role.value,
                )
            )

    async def get(self, workspace_id: str, user_id: str) -> Membership | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(MembershipRow).where(
                    MembershipRow.workspace_id == workspace_id,
                    MembershipRow.user_id == user_id,
                )
            )
            return _membership_to_domain(row) if row else None

    async def list_for_workspace(self, workspace_id: str) -> list[tuple[Membership, User]]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(MembershipRow, UserRow)
                .join(UserRow, UserRow.id == MembershipRow.user_id)
                .where(MembershipRow.workspace_id == workspace_id)
                .order_by(MembershipRow.id)
            )
            return [(_membership_to_domain(m), _user_to_domain(u)) for m, u in rows.all()]

    async def save(self, membership: Membership) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(MembershipRow, membership.id)
            if row is None:
                raise NotFoundError("Membership not found")
            row.role = membership.role.value

    async def remove(self, membership_id: str) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(MembershipRow, membership_id)
            if row is not None:
                await session.delete(row)


class SqlRefreshTokenRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, record: RefreshTokenRecord) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                RefreshTokenRow(
                    id=record.id,
                    user_id=record.user_id,
                    family_id=record.family_id,
                    token_hash=record.token_hash,
                    expires_at=record.expires_at,
                    used_at=record.used_at,
                    revoked_at=record.revoked_at,
                )
            )

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RefreshTokenRow).where(RefreshTokenRow.token_hash == token_hash)
            )
            if row is None:
                return None
            return RefreshTokenRecord(
                id=row.id,
                user_id=row.user_id,
                family_id=row.family_id,
                token_hash=row.token_hash,
                expires_at=row.expires_at,
                used_at=row.used_at,
                revoked_at=row.revoked_at,
            )

    async def mark_used(self, record_id: str, now: datetime) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(RefreshTokenRow).where(RefreshTokenRow.id == record_id).values(used_at=now)
            )

    async def revoke_family(self, family_id: str, now: datetime) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(RefreshTokenRow)
                .where(RefreshTokenRow.family_id == family_id, RefreshTokenRow.revoked_at.is_(None))
                .values(revoked_at=now)
            )


class SqlVerificationTokenRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, user_id: str, token_hash: str, expires_at: datetime) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                EmailVerificationTokenRow(
                    token_hash=token_hash, user_id=user_id, expires_at=expires_at
                )
            )

    async def consume(self, token_hash: str, now: datetime) -> str | None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(EmailVerificationTokenRow, token_hash)
            if row is None or row.used_at is not None or row.expires_at <= now:
                return None
            row.used_at = now
            return row.user_id


def _user_to_domain(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        email_verified=row.email_verified,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _workspace_to_domain(row: WorkspaceRow) -> Workspace:
    return Workspace(
        id=row.id,
        slug=row.slug,
        name=row.name,
        kind=WorkspaceKind(row.kind),
        plan=row.plan,
        settings=dict(row.settings),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _membership_to_domain(row: MembershipRow) -> Membership:
    return Membership(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        role=Role(row.role),
    )
