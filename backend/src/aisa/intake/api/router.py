from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from aisa.intake.domain.models import Message, RequirementDoc
from aisa.platform.api.deps import ContainerDep, CurrentActor

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/projects/{project_id}", tags=["intake"]
)


class PostMessageRequest(BaseModel):
    text: str


class PostMessageResponse(BaseModel):
    thread_id: str
    run_id: str
    resumed: bool


class MessageResponse(BaseModel):
    id: str
    role: str
    content: dict[str, object]
    run_id: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, message: Message) -> "MessageResponse":
        return cls(
            id=message.id,
            role=message.role.value,
            content=message.content,
            run_id=message.run_id,
            created_at=message.created_at,
        )


class RequirementsResponse(BaseModel):
    version: int
    status: str
    content: dict[str, object]
    created_by: str
    created_at: datetime

    @classmethod
    def from_domain(cls, doc: RequirementDoc) -> "RequirementsResponse":
        return cls(
            version=doc.version,
            status=doc.status.value,
            content=doc.content,
            created_by=doc.created_by,
            created_at=doc.created_at,
        )


@router.get("/messages")
async def list_messages(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> list[MessageResponse]:
    messages = await container.list_messages.execute(actor, project_id)
    return [MessageResponse.from_domain(m) for m in messages]


@router.post("/messages", status_code=201)
async def post_message(
    project_id: str,
    body: PostMessageRequest,
    actor: CurrentActor,
    container: ContainerDep,
) -> PostMessageResponse:
    result = await container.post_message.execute(actor, project_id, body.text)
    return PostMessageResponse(
        thread_id=result.thread_id, run_id=result.run_id, resumed=result.resumed
    )


@router.get("/requirements")
async def get_requirements(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> RequirementsResponse:
    doc = await container.get_requirements.execute(actor, project_id)
    return RequirementsResponse.from_domain(doc)


@router.post("/requirements/confirm")
async def confirm_requirements(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> RequirementsResponse:
    doc = await container.confirm_requirements.execute(actor, project_id)
    return RequirementsResponse.from_domain(doc)
