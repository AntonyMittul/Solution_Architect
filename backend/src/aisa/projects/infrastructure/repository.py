from sqlalchemy import select

from aisa.projects.domain.project import Project, ProjectStatus
from aisa.projects.infrastructure.tables import ProjectRow
from aisa.shared.db import SessionFactory, tenant_session
from aisa.shared.errors import NotFoundError


class SqlProjectRepository:
    """Workspace-scoped repository. Every query runs in a tenant session
    (SET LOCAL app.workspace_id) so Postgres RLS enforces isolation beneath
    the explicit WHERE clauses — belt and suspenders (doc 09 §3)."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, project: Project) -> None:
        async with tenant_session(self._session_factory, project.workspace_id) as session:
            session.add(_to_row(project))

    async def get(
        self, workspace_id: str, project_id: str, include_deleted: bool = False
    ) -> Project:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(
                select(ProjectRow).where(
                    ProjectRow.id == project_id, ProjectRow.workspace_id == workspace_id
                )
            )
            if row is None or (row.deleted_at is not None and not include_deleted):
                raise NotFoundError(f"Project '{project_id}' not found")
            return _to_domain(row)

    async def list_active(self, workspace_id: str) -> list[Project]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            rows = await session.scalars(
                select(ProjectRow)
                .where(ProjectRow.workspace_id == workspace_id, ProjectRow.deleted_at.is_(None))
                .order_by(ProjectRow.id)
            )
            return [_to_domain(row) for row in rows]

    async def save(self, project: Project) -> None:
        async with tenant_session(self._session_factory, project.workspace_id) as session:
            row = await session.scalar(
                select(ProjectRow).where(
                    ProjectRow.id == project.id,
                    ProjectRow.workspace_id == project.workspace_id,
                )
            )
            if row is None:
                raise NotFoundError(f"Project '{project.id}' not found")
            row.name = project.name
            row.description = project.description
            row.status = project.status.value
            row.settings = dict(project.settings)
            row.updated_at = project.updated_at
            row.deleted_at = project.deleted_at


def _to_row(project: Project) -> ProjectRow:
    return ProjectRow(
        id=project.id,
        workspace_id=project.workspace_id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        settings=dict(project.settings),
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        deleted_at=project.deleted_at,
    )


def _to_domain(row: ProjectRow) -> Project:
    return Project(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        status=ProjectStatus(row.status),
        settings=dict(row.settings),
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )
