from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from aisa.identity.domain.models import Membership, Role, User, Workspace
from aisa.platform.api.deps import ContainerDep, CurrentActor, CurrentUserId

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


class WorkspaceResponse(BaseModel):
    id: str
    slug: str
    name: str
    kind: str
    plan: str
    role: str

    @classmethod
    def from_domain(cls, workspace: Workspace, role: Role) -> "WorkspaceResponse":
        return cls(
            id=workspace.id,
            slug=workspace.slug,
            name=workspace.name,
            kind=workspace.kind.value,
            plan=workspace.plan,
            role=role.value,
        )


class CreateWorkspaceRequest(BaseModel):
    name: str


class MemberResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str

    @classmethod
    def from_domain(cls, membership: Membership, user: User) -> "MemberResponse":
        return cls(user_id=user.id, email=user.email, name=user.name, role=membership.role.value)


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: Role


class ChangeRoleRequest(BaseModel):
    role: Role


@router.get("")
async def list_my_workspaces(
    user_id: CurrentUserId, container: ContainerDep
) -> list[WorkspaceResponse]:
    results = await container.list_my_workspaces.execute(user_id)
    return [WorkspaceResponse.from_domain(ws, role) for ws, role in results]


@router.post("", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest, user_id: CurrentUserId, container: ContainerDep
) -> WorkspaceResponse:
    workspace = await container.create_workspace.execute(user_id=user_id, name=body.name)
    return WorkspaceResponse.from_domain(workspace, Role.OWNER)


@router.get("/{workspace_id}/members")
async def list_members(actor: CurrentActor, container: ContainerDep) -> list[MemberResponse]:
    results = await container.list_members.execute(actor)
    return [MemberResponse.from_domain(m, u) for m, u in results]


@router.post("/{workspace_id}/members", status_code=201)
async def invite_member(
    body: InviteMemberRequest, actor: CurrentActor, container: ContainerDep
) -> dict[str, str]:
    membership = await container.invite_member.execute(actor, email=body.email, role=body.role)
    return {"user_id": membership.user_id, "role": membership.role.value}


@router.patch("/{workspace_id}/members/{target_user_id}")
async def change_member_role(
    target_user_id: str, body: ChangeRoleRequest, actor: CurrentActor, container: ContainerDep
) -> dict[str, str]:
    membership = await container.change_member_role.execute(
        actor, target_user_id=target_user_id, role=body.role
    )
    return {"user_id": membership.user_id, "role": membership.role.value}


@router.delete("/{workspace_id}/members/{target_user_id}", status_code=204)
async def remove_member(target_user_id: str, actor: CurrentActor, container: ContainerDep) -> None:
    await container.remove_member.execute(actor, target_user_id=target_user_id)
