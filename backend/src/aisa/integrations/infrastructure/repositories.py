from sqlalchemy import delete, select

from aisa.integrations.domain.models import (
    InvocationStatus,
    McpServer,
    PlanStatus,
    ProvisioningPlan,
    ServerStatus,
    ToolInvocation,
    TransportKind,
    TrustLevel,
)
from aisa.integrations.infrastructure.tables import (
    McpServerRow,
    ProvisioningPlanRow,
    ToolInvocationRow,
)
from aisa.shared.db import SessionFactory, tenant_session
from aisa.shared.errors import NotFoundError

# Every query runs in a tenant session so Postgres RLS enforces isolation.


class SqlMcpServerRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, server: McpServer) -> None:
        async with tenant_session(self._session_factory, server.workspace_id) as session:
            session.add(_server_row(server))

    async def get(self, workspace_id: str, server_id: str) -> McpServer:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.scalar(select(McpServerRow).where(McpServerRow.id == server_id))
            if row is None:
                raise NotFoundError(f"MCP server '{server_id}' not found")
            return _server(row)

    async def list_all(self, workspace_id: str) -> list[McpServer]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            rows = await session.scalars(select(McpServerRow).order_by(McpServerRow.name))
            return [_server(row) for row in rows]

    async def list_active(self, workspace_id: str) -> list[McpServer]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            rows = await session.scalars(
                select(McpServerRow)
                .where(McpServerRow.status == ServerStatus.ACTIVE.value)
                .order_by(McpServerRow.name)
            )
            return [_server(row) for row in rows]

    async def save(self, server: McpServer) -> None:
        async with tenant_session(self._session_factory, server.workspace_id) as session:
            row = await session.get(McpServerRow, server.id)
            if row is None:
                raise NotFoundError(f"MCP server '{server.id}' not found")
            row.tool_allowlist = list(server.tool_allowlist)
            row.trust = server.trust.value
            row.status = server.status.value

    async def remove(self, workspace_id: str, server_id: str) -> None:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.get(McpServerRow, server_id)
            if row is not None:
                await session.delete(row)


class SqlProvisioningRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, plan: ProvisioningPlan) -> None:
        async with tenant_session(self._session_factory, plan.workspace_id) as session:
            session.add(_plan_row(plan))
            for ordinal, invocation in enumerate(plan.invocations):
                session.add(_invocation_row(plan, invocation, ordinal))

    async def get(self, workspace_id: str, plan_id: str) -> ProvisioningPlan:
        async with tenant_session(self._session_factory, workspace_id) as session:
            row = await session.get(ProvisioningPlanRow, plan_id)
            if row is None:
                raise NotFoundError(f"Provisioning plan '{plan_id}' not found")
            invocations = await session.scalars(
                select(ToolInvocationRow)
                .where(ToolInvocationRow.plan_id == plan_id)
                .order_by(ToolInvocationRow.ordinal)
            )
            return _plan(row, list(invocations))

    async def list_for_project(self, workspace_id: str, project_id: str) -> list[ProvisioningPlan]:
        async with tenant_session(self._session_factory, workspace_id) as session:
            rows = await session.scalars(
                select(ProvisioningPlanRow)
                .where(ProvisioningPlanRow.project_id == project_id)
                .order_by(ProvisioningPlanRow.id.desc())
            )
            plans: list[ProvisioningPlan] = []
            for row in rows:
                invocations = await session.scalars(
                    select(ToolInvocationRow)
                    .where(ToolInvocationRow.plan_id == row.id)
                    .order_by(ToolInvocationRow.ordinal)
                )
                plans.append(_plan(row, list(invocations)))
            return plans

    async def save(self, plan: ProvisioningPlan) -> None:
        # Plans are rewritten wholesale (invocation count never changes after
        # creation); simplest is to replace the invocation rows.
        async with tenant_session(self._session_factory, plan.workspace_id) as session:
            row = await session.get(ProvisioningPlanRow, plan.id)
            if row is None:
                raise NotFoundError(f"Provisioning plan '{plan.id}' not found")
            row.status = plan.status.value
            await session.execute(
                delete(ToolInvocationRow).where(ToolInvocationRow.plan_id == plan.id)
            )
            for ordinal, invocation in enumerate(plan.invocations):
                session.add(_invocation_row(plan, invocation, ordinal))


def _server_row(server: McpServer) -> McpServerRow:
    return McpServerRow(
        id=server.id,
        workspace_id=server.workspace_id,
        name=server.name,
        transport=server.transport.value,
        endpoint=server.endpoint,
        trust=server.trust.value,
        tool_allowlist=list(server.tool_allowlist),
        status=server.status.value,
        created_by=server.created_by,
        created_at=server.created_at,
    )


def _server(row: McpServerRow) -> McpServer:
    return McpServer(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        transport=TransportKind(row.transport),
        endpoint=row.endpoint,
        trust=TrustLevel(row.trust),
        tool_allowlist=list(row.tool_allowlist),
        status=ServerStatus(row.status),
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _plan_row(plan: ProvisioningPlan) -> ProvisioningPlanRow:
    return ProvisioningPlanRow(
        id=plan.id,
        workspace_id=plan.workspace_id,
        project_id=plan.project_id,
        goal=plan.goal,
        summary=plan.summary,
        status=plan.status.value,
        created_by=plan.created_by,
        created_at=plan.created_at,
    )


def _invocation_row(
    plan: ProvisioningPlan, invocation: ToolInvocation, ordinal: int
) -> ToolInvocationRow:
    return ToolInvocationRow(
        id=invocation.id,
        workspace_id=plan.workspace_id,
        plan_id=plan.id,
        ordinal=ordinal,
        server_id=invocation.server_id,
        tool_name=invocation.tool_name,
        arguments=dict(invocation.arguments),
        rationale=invocation.rationale,
        status=invocation.status.value,
        result=invocation.result,
    )


def _plan(row: ProvisioningPlanRow, invocation_rows: list[ToolInvocationRow]) -> ProvisioningPlan:
    return ProvisioningPlan(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        goal=row.goal,
        summary=row.summary,
        status=PlanStatus(row.status),
        created_by=row.created_by,
        created_at=row.created_at,
        invocations=[
            ToolInvocation(
                id=inv.id,
                server_id=inv.server_id,
                tool_name=inv.tool_name,
                arguments={str(k): str(v) for k, v in inv.arguments.items()},
                rationale=inv.rationale,
                status=InvocationStatus(inv.status),
                result=inv.result,
            )
            for inv in invocation_rows
        ],
    )
