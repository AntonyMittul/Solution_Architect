from datetime import datetime

from sqlalchemy import func, select

from aisa.intake.domain.models import (
    Message,
    RequirementDoc,
    RequirementStatus,
    Thread,
    ThreadRole,
)
from aisa.intake.infrastructure.tables import MessageRow, RequirementDocRow, ThreadRow
from aisa.shared.clock import Clock
from aisa.shared.db import SessionFactory, tenant_session
from aisa.shared.errors import NotFoundError
from aisa.shared.ids import new_id

# All queries run inside a tenant session (SET LOCAL app.workspace_id) so
# Postgres RLS enforces isolation beneath the explicit WHERE clauses.


class SqlThreadRepository:
    def __init__(self, session_factory: SessionFactory, clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def ensure_for_project(self, workspace_id: str, project_id: str) -> Thread:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(select(ThreadRow).where(ThreadRow.project_id == project_id))
            if row is None:
                row = ThreadRow(
                    id=new_id(),
                    workspace_id=workspace_id,
                    project_id=project_id,
                    created_at=self._clock.now(),
                )
                session.add(row)
                await session.flush()
            return _thread(row)

    async def get_for_project(self, workspace_id: str, project_id: str) -> Thread | None:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(select(ThreadRow).where(ThreadRow.project_id == project_id))
            return _thread(row) if row is not None else None


class SqlMessageRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def append(
        self,
        workspace_id: str,
        thread_id: str,
        *,
        role: ThreadRole,
        content: dict[str, object],
        run_id: str | None,
        now: datetime,
    ) -> Message:
        row = MessageRow(
            id=new_id(),
            workspace_id=workspace_id,
            thread_id=thread_id,
            role=role.value,
            content=content,
            run_id=run_id,
            created_at=now,
        )
        async with tenant_session(self._session_factory, workspace_id) as session:
            session.add(row)
        return _message(row)

    async def list_for_thread(self, workspace_id: str, thread_id: str) -> list[Message]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            rows = await session.scalars(
                select(MessageRow)
                .where(MessageRow.thread_id == thread_id)
                .order_by(MessageRow.id)  # ULID ids are chronological
            )
            return [_message(row) for row in rows]


class SqlRequirementRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def append_version(
        self,
        workspace_id: str,
        project_id: str,
        *,
        content: dict[str, object],
        created_by: str,
        now: datetime,
    ) -> RequirementDoc:
        async with tenant_session(self._session_factory, workspace_id) as session:
            current_max = await session.scalar(
                select(func.max(RequirementDocRow.version)).where(
                    RequirementDocRow.project_id == project_id
                )
            )
            row = RequirementDocRow(
                id=new_id(),
                workspace_id=workspace_id,
                project_id=project_id,
                version=(current_max or 0) + 1,
                status=RequirementStatus.DRAFT.value,
                content=content,
                created_by=created_by,
                created_at=now,
            )
            session.add(row)
            await session.flush()
            return _requirement(row)

    async def latest(self, workspace_id: str, project_id: str) -> RequirementDoc | None:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(
                select(RequirementDocRow)
                .where(RequirementDocRow.project_id == project_id)
                .order_by(RequirementDocRow.version.desc())
                .limit(1)
            )
            return _requirement(row) if row is not None else None

    async def confirm_latest(self, workspace_id: str, project_id: str) -> RequirementDoc:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(
                select(RequirementDocRow)
                .where(RequirementDocRow.project_id == project_id)
                .order_by(RequirementDocRow.version.desc())
                .limit(1)
            )
            if row is None:
                raise NotFoundError("No requirements to confirm")
            doc = _requirement(row)
            doc.confirm()
            row.status = doc.status.value
            return doc


def _thread(row: ThreadRow) -> Thread:
    return Thread(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        created_at=row.created_at,
    )


def _message(row: MessageRow) -> Message:
    return Message(
        id=row.id,
        workspace_id=row.workspace_id,
        thread_id=row.thread_id,
        role=ThreadRole(row.role),
        content=dict(row.content),
        run_id=row.run_id,
        created_at=row.created_at,
    )


def _requirement(row: RequirementDocRow) -> RequirementDoc:
    return RequirementDoc(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        version=row.version,
        status=RequirementStatus(row.status),
        content=dict(row.content),
        created_by=row.created_by,
        created_at=row.created_at,
    )
