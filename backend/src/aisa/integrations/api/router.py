from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from aisa.integrations.domain.models import (
    McpServer,
    ProvisioningPlan,
    ServerStatus,
    ToolDescriptor,
    ToolInvocation,
    TransportKind,
    TrustLevel,
)
from aisa.platform.api.deps import ContainerDep, CurrentActor

mcp_server_router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/mcp-servers", tags=["mcp"])
provisioning_router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/projects/{project_id}/provisioning", tags=["mcp"]
)


class McpServerResponse(BaseModel):
    id: str
    name: str
    transport: str
    endpoint: str
    trust: str
    tool_allowlist: list[str]
    status: str
    created_at: datetime

    @classmethod
    def from_domain(cls, server: McpServer) -> "McpServerResponse":
        return cls(
            id=server.id,
            name=server.name,
            transport=server.transport.value,
            endpoint=server.endpoint,
            trust=server.trust.value,
            tool_allowlist=server.tool_allowlist,
            status=server.status.value,
            created_at=server.created_at,
        )


class RegisterServerRequest(BaseModel):
    name: str
    transport: TransportKind = TransportKind.STREAMABLE_HTTP
    endpoint: str = ""
    trust: TrustLevel = TrustLevel.UNTRUSTED
    tool_allowlist: list[str] = []


class UpdateServerRequest(BaseModel):
    tool_allowlist: list[str] | None = None
    trust: TrustLevel | None = None
    status: ServerStatus | None = None


class ToolDescriptorResponse(BaseModel):
    name: str
    description: str

    @classmethod
    def from_domain(cls, tool: ToolDescriptor) -> "ToolDescriptorResponse":
        return cls(name=tool.name, description=tool.description)


class InvocationResponse(BaseModel):
    id: str
    server_id: str
    tool_name: str
    arguments: dict[str, str]
    rationale: str
    status: str
    result: dict[str, object] | None

    @classmethod
    def from_domain(cls, invocation: ToolInvocation) -> "InvocationResponse":
        return cls(
            id=invocation.id,
            server_id=invocation.server_id,
            tool_name=invocation.tool_name,
            arguments=invocation.arguments,
            rationale=invocation.rationale,
            status=invocation.status.value,
            result=invocation.result,
        )


class PlanResponse(BaseModel):
    id: str
    project_id: str
    goal: str
    summary: str
    status: str
    created_at: datetime
    invocations: list[InvocationResponse]

    @classmethod
    def from_domain(cls, plan: ProvisioningPlan) -> "PlanResponse":
        return cls(
            id=plan.id,
            project_id=plan.project_id,
            goal=plan.goal,
            summary=plan.summary,
            status=plan.status.value,
            created_at=plan.created_at,
            invocations=[InvocationResponse.from_domain(i) for i in plan.invocations],
        )


class CreatePlanRequest(BaseModel):
    goal: str


# ---- MCP servers -----------------------------------------------------------


@mcp_server_router.get("")
async def list_servers(actor: CurrentActor, container: ContainerDep) -> list[McpServerResponse]:
    servers = await container.list_mcp_servers.execute(actor)
    return [McpServerResponse.from_domain(s) for s in servers]


@mcp_server_router.post("", status_code=201)
async def register_server(
    body: RegisterServerRequest, actor: CurrentActor, container: ContainerDep
) -> McpServerResponse:
    server = await container.register_mcp_server.execute(
        actor,
        name=body.name,
        transport=body.transport,
        endpoint=body.endpoint,
        trust=body.trust,
        tool_allowlist=body.tool_allowlist,
    )
    return McpServerResponse.from_domain(server)


@mcp_server_router.patch("/{server_id}")
async def update_server(
    server_id: str, body: UpdateServerRequest, actor: CurrentActor, container: ContainerDep
) -> McpServerResponse:
    server = await container.update_mcp_server.execute(
        actor, server_id, tool_allowlist=body.tool_allowlist, trust=body.trust, status=body.status
    )
    return McpServerResponse.from_domain(server)


@mcp_server_router.delete("/{server_id}", status_code=204)
async def delete_server(server_id: str, actor: CurrentActor, container: ContainerDep) -> None:
    await container.delete_mcp_server.execute(actor, server_id)


@mcp_server_router.get("/{server_id}/tools")
async def discover_tools(
    server_id: str, actor: CurrentActor, container: ContainerDep
) -> list[ToolDescriptorResponse]:
    tools = await container.discover_server_tools.execute(actor, server_id)
    return [ToolDescriptorResponse.from_domain(t) for t in tools]


# ---- Provisioning plans ----------------------------------------------------


@provisioning_router.get("/plans")
async def list_plans(
    project_id: str, actor: CurrentActor, container: ContainerDep
) -> list[PlanResponse]:
    plans = await container.list_provisioning_plans.execute(actor, project_id)
    return [PlanResponse.from_domain(p) for p in plans]


@provisioning_router.post("/plans", status_code=201)
async def create_plan(
    project_id: str, body: CreatePlanRequest, actor: CurrentActor, container: ContainerDep
) -> PlanResponse:
    plan = await container.create_provisioning_plan.execute(actor, project_id, body.goal)
    return PlanResponse.from_domain(plan)


@provisioning_router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, actor: CurrentActor, container: ContainerDep) -> PlanResponse:
    plan = await container.get_provisioning_plan.execute(actor, plan_id)
    return PlanResponse.from_domain(plan)


@provisioning_router.post("/plans/{plan_id}/approve")
async def approve_plan(plan_id: str, actor: CurrentActor, container: ContainerDep) -> PlanResponse:
    plan = await container.approve_provisioning_plan.execute(actor, plan_id)
    return PlanResponse.from_domain(plan)


@provisioning_router.post("/plans/{plan_id}/reject")
async def reject_plan(plan_id: str, actor: CurrentActor, container: ContainerDep) -> PlanResponse:
    plan = await container.reject_provisioning_plan.execute(actor, plan_id)
    return PlanResponse.from_domain(plan)
