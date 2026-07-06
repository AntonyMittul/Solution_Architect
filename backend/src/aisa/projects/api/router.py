from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from aisa.platform.api.deps import ContainerDep, CurrentActor
from aisa.projects.domain.project import Project, ProjectStatus

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None
    settings: dict[str, object] = {}


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: ProjectStatus | None = None
    settings: dict[str, object] | None = None


class ProjectResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None
    status: str
    settings: dict[str, object]
    created_by: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_domain(cls, project: Project) -> "ProjectResponse":
        return cls(
            id=project.id,
            workspace_id=project.workspace_id,
            name=project.name,
            description=project.description,
            status=project.status.value,
            settings=project.settings,
            created_by=project.created_by,
            created_at=project.created_at,
            updated_at=project.updated_at,
            deleted_at=project.deleted_at,
        )


@router.get("")
async def list_projects(actor: CurrentActor, container: ContainerDep) -> list[ProjectResponse]:
    projects = await container.list_projects.execute(actor)
    return [ProjectResponse.from_domain(p) for p in projects]


@router.post("", status_code=201)
async def create_project(
    body: CreateProjectRequest, actor: CurrentActor, container: ContainerDep
) -> ProjectResponse:
    project = await container.create_project.execute(
        actor, name=body.name, description=body.description, settings=dict(body.settings)
    )
    return ProjectResponse.from_domain(project)


@router.get("/{project_id}")
async def get_project(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> ProjectResponse:
    project = await container.get_project.execute(actor, project_id)
    return ProjectResponse.from_domain(project)


@router.patch("/{project_id}")
async def update_project(
    project_id: str, body: UpdateProjectRequest, actor: CurrentActor, container: ContainerDep
) -> ProjectResponse:
    project = await container.update_project.execute(
        actor,
        project_id,
        name=body.name,
        description=body.description,
        status=body.status,
        settings=dict(body.settings) if body.settings is not None else None,
    )
    return ProjectResponse.from_domain(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, actor: CurrentActor, container: ContainerDep) -> None:
    await container.delete_project.execute(actor, project_id)


@router.post("/{project_id}/restore")
async def restore_project(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> ProjectResponse:
    project = await container.restore_project.execute(actor, project_id)
    return ProjectResponse.from_domain(project)
