from typing import Protocol

from aisa.artifacts.domain.models import Artifact, ArtifactType, ArtifactVersion


class ArtifactRepository(Protocol):
    """Workspace-scoped; implementations run inside a tenant session so RLS
    applies beneath the explicit WHERE clauses."""

    async def ensure(self, workspace_id: str, project_id: str, type: ArtifactType) -> Artifact: ...

    async def append_version(
        self,
        workspace_id: str,
        artifact_id: str,
        *,
        content: dict[str, object],
        provenance: dict[str, object],
    ) -> ArtifactVersion: ...

    async def set_dependencies(
        self, workspace_id: str, artifact_id: str, depends_on_ids: list[str]
    ) -> None: ...

    async def list_latest(
        self, workspace_id: str, project_id: str
    ) -> list[tuple[Artifact, ArtifactVersion | None]]: ...

    async def get_latest(
        self, workspace_id: str, project_id: str, type: ArtifactType
    ) -> tuple[Artifact, ArtifactVersion | None] | None: ...

    async def list_versions(
        self, workspace_id: str, project_id: str, type: ArtifactType
    ) -> list[ArtifactVersion]: ...

    async def mark_stale(self, workspace_id: str, artifact_ids: list[str], stale: bool) -> None: ...

    async def dependents_of(self, workspace_id: str, artifact_id: str) -> list[str]:
        """Artifact ids that directly depend on the given artifact."""
        ...
