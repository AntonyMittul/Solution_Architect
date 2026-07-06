from aisa.artifacts.application.ports import ArtifactRepository
from aisa.artifacts.domain.models import Artifact, ArtifactType, ArtifactVersion
from aisa.shared.authz import Actor, Permission
from aisa.shared.errors import NotFoundError


class ListArtifacts:
    def __init__(self, artifacts: ArtifactRepository) -> None:
        self._artifacts = artifacts

    async def execute(
        self, actor: Actor, project_id: str
    ) -> list[tuple[Artifact, ArtifactVersion | None]]:
        actor.require(Permission.PROJECT_READ)
        return await self._artifacts.list_latest(actor.workspace_id, project_id)


class GetArtifact:
    def __init__(self, artifacts: ArtifactRepository) -> None:
        self._artifacts = artifacts

    async def execute(
        self, actor: Actor, project_id: str, type: ArtifactType
    ) -> tuple[Artifact, ArtifactVersion | None]:
        actor.require(Permission.PROJECT_READ)
        result = await self._artifacts.get_latest(actor.workspace_id, project_id, type)
        if result is None:
            raise NotFoundError(f"No '{type}' artifact for this project")
        return result


class ListArtifactVersions:
    def __init__(self, artifacts: ArtifactRepository) -> None:
        self._artifacts = artifacts

    async def execute(
        self, actor: Actor, project_id: str, type: ArtifactType
    ) -> list[ArtifactVersion]:
        actor.require(Permission.PROJECT_READ)
        return await self._artifacts.list_versions(actor.workspace_id, project_id, type)
