from fastapi import APIRouter, Response

from aisa.platform.api.deps import ContainerDep, CurrentActor

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/projects/{project_id}", tags=["exports"]
)


@router.get("/export")
async def export_project(project_id: str, actor: CurrentActor, container: ContainerDep) -> Response:
    result = await container.build_project_export.execute(actor, project_id)
    return Response(
        content=result.data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )
