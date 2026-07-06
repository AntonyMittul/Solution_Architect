from fastapi import APIRouter
from pydantic import BaseModel

from aisa.platform.api.deps import ContainerDep, CurrentActor

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/projects/{project_id}", tags=["blueprint"]
)


class StartBlueprintResponse(BaseModel):
    run_id: str
    status: str


@router.post("/blueprint", status_code=201)
async def start_blueprint(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> StartBlueprintResponse:
    run = await container.create_blueprint_run.execute(actor, project_id)
    return StartBlueprintResponse(run_id=run.id, status=run.status.value)
