from typing import Protocol

from aisa.projects.domain.project import Project


class ProjectRepository(Protocol):
    """All operations are workspace-scoped; implementations must run inside a
    tenant session so Postgres RLS applies as the backstop."""

    async def add(self, project: Project) -> None: ...

    async def get(
        self, workspace_id: str, project_id: str, include_deleted: bool = False
    ) -> Project:
        """Raises NotFoundError."""
        ...

    async def list_active(self, workspace_id: str) -> list[Project]: ...

    async def save(self, project: Project) -> None: ...
