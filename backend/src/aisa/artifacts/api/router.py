from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from aisa.artifacts.domain.models import Artifact, ArtifactType, ArtifactVersion
from aisa.platform.api.deps import ContainerDep, CurrentActor

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/projects/{project_id}/artifacts",
    tags=["artifacts"],
)


class ArtifactVersionResponse(BaseModel):
    version: int
    content: dict[str, object]
    provenance: dict[str, object]
    created_at: datetime

    @classmethod
    def from_domain(cls, v: ArtifactVersion) -> "ArtifactVersionResponse":
        return cls(
            version=v.version, content=v.content, provenance=v.provenance, created_at=v.created_at
        )


class ArtifactResponse(BaseModel):
    type: str
    is_stale: bool
    latest: ArtifactVersionResponse | None

    @classmethod
    def from_domain(cls, artifact: Artifact, latest: ArtifactVersion | None) -> "ArtifactResponse":
        return cls(
            type=artifact.type.value,
            is_stale=artifact.is_stale,
            latest=ArtifactVersionResponse.from_domain(latest) if latest else None,
        )


@router.get("")
async def list_artifacts(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> list[ArtifactResponse]:
    items = await container.list_artifacts.execute(actor, project_id)
    return [ArtifactResponse.from_domain(a, v) for a, v in items]


@router.get("/{artifact_type}")
async def get_artifact(
    project_id: str, artifact_type: ArtifactType, actor: CurrentActor, container: ContainerDep
) -> ArtifactResponse:
    artifact, latest = await container.get_artifact.execute(actor, project_id, artifact_type)
    return ArtifactResponse.from_domain(artifact, latest)


@router.get("/{artifact_type}/versions")
async def list_versions(
    project_id: str, artifact_type: ArtifactType, actor: CurrentActor, container: ContainerDep
) -> list[ArtifactVersionResponse]:
    versions = await container.list_artifact_versions.execute(actor, project_id, artifact_type)
    return [ArtifactVersionResponse.from_domain(v) for v in versions]
