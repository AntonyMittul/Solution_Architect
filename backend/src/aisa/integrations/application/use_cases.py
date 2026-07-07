from collections.abc import Callable

import structlog

from aisa.integrations.application.agent import PROMPT_VERSION, Provisioner
from aisa.integrations.application.governor import ToolGovernor
from aisa.integrations.application.ports import (
    McpClient,
    McpServerRepository,
    ProvisioningRepository,
)
from aisa.integrations.domain.models import (
    InvocationStatus,
    McpServer,
    PlanStatus,
    ProvisioningPlan,
    ServerStatus,
    ToolDescriptor,
    ToolInvocation,
    TransportKind,
    TrustLevel,
)
from aisa.llm.application.service import LLMContext
from aisa.shared.audit import AuditEntry, AuditLogger
from aisa.shared.authz import Actor, Permission
from aisa.shared.clock import Clock
from aisa.shared.errors import DomainValidationError, InvalidStateError, NotFoundError

logger = structlog.get_logger(__name__)


class RegisterMcpServer:
    def __init__(
        self,
        servers: McpServerRepository,
        audit: AuditLogger,
        clock: Clock,
        id_factory: Callable[[], str],
    ) -> None:
        self._servers = servers
        self._audit = audit
        self._clock = clock
        self._id_factory = id_factory

    async def execute(
        self,
        actor: Actor,
        *,
        name: str,
        transport: TransportKind,
        endpoint: str,
        trust: TrustLevel,
        tool_allowlist: list[str],
    ) -> McpServer:
        actor.require(Permission.WORKSPACE_MANAGE)
        if not name.strip():
            raise DomainValidationError("Server name must not be empty")
        server = McpServer(
            id=self._id_factory(),
            workspace_id=actor.workspace_id,
            name=name.strip(),
            transport=transport,
            endpoint=endpoint.strip(),
            trust=trust,
            tool_allowlist=sorted(set(tool_allowlist)),
            status=ServerStatus.ACTIVE,
            created_by=actor.user_id,
            created_at=self._clock.now(),
        )
        await self._servers.add(server)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="mcp.server.registered",
                workspace_id=actor.workspace_id,
                target=f"mcp:{server.id}",
                metadata={"name": server.name, "tools": len(server.tool_allowlist)},
            )
        )
        return server


class ListMcpServers:
    def __init__(self, servers: McpServerRepository) -> None:
        self._servers = servers

    async def execute(self, actor: Actor) -> list[McpServer]:
        actor.require(Permission.PROJECT_READ)
        return await self._servers.list_all(actor.workspace_id)


class UpdateMcpServer:
    def __init__(self, servers: McpServerRepository, audit: AuditLogger) -> None:
        self._servers = servers
        self._audit = audit

    async def execute(
        self,
        actor: Actor,
        server_id: str,
        *,
        tool_allowlist: list[str] | None = None,
        trust: TrustLevel | None = None,
        status: ServerStatus | None = None,
    ) -> McpServer:
        actor.require(Permission.WORKSPACE_MANAGE)
        server = await self._servers.get(actor.workspace_id, server_id)
        if tool_allowlist is not None:
            server.tool_allowlist = sorted(set(tool_allowlist))
        if trust is not None:
            server.trust = trust
        if status is not None:
            server.status = status
        await self._servers.save(server)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="mcp.server.updated",
                workspace_id=actor.workspace_id,
                target=f"mcp:{server.id}",
            )
        )
        return server


class DeleteMcpServer:
    def __init__(self, servers: McpServerRepository, audit: AuditLogger) -> None:
        self._servers = servers
        self._audit = audit

    async def execute(self, actor: Actor, server_id: str) -> None:
        actor.require(Permission.WORKSPACE_MANAGE)
        await self._servers.get(actor.workspace_id, server_id)  # 404 if absent
        await self._servers.remove(actor.workspace_id, server_id)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="mcp.server.deleted",
                workspace_id=actor.workspace_id,
                target=f"mcp:{server_id}",
            )
        )


class DiscoverServerTools:
    def __init__(self, servers: McpServerRepository, client: McpClient) -> None:
        self._servers = servers
        self._client = client

    async def execute(self, actor: Actor, server_id: str) -> list[ToolDescriptor]:
        actor.require(Permission.PROJECT_READ)
        server = await self._servers.get(actor.workspace_id, server_id)
        return await self._client.discover(server)


class CreateProvisioningPlan:
    """Ask the provisioner to plan tool calls for a goal, then keep only the
    calls the governor allows. The result is stored PROPOSED — nothing runs."""

    def __init__(
        self,
        servers: McpServerRepository,
        plans: ProvisioningRepository,
        client: McpClient,
        provisioner: Provisioner,
        governor: ToolGovernor,
        clock: Clock,
        id_factory: Callable[[], str],
    ) -> None:
        self._servers = servers
        self._plans = plans
        self._client = client
        self._provisioner = provisioner
        self._governor = governor
        self._clock = clock
        self._id_factory = id_factory

    async def execute(self, actor: Actor, project_id: str, goal: str) -> ProvisioningPlan:
        actor.require(Permission.RUN_TRIGGER)
        if not actor.email_verified:
            raise NotFoundError("Verify your email address before provisioning")
        if not goal.strip():
            raise DomainValidationError("Provisioning goal must not be empty")

        servers = await self._servers.list_active(actor.workspace_id)
        tools_by_server: dict[str, tuple[McpServer, list[ToolDescriptor]]] = {}
        for server in servers:
            allowed = [t for t in await self._client.discover(server) if server.allows(t.name)]
            if allowed:
                tools_by_server[server.id] = (server, allowed)
        if not tools_by_server:
            raise NotFoundError(
                "Register an MCP server and allowlist at least one tool before provisioning"
            )

        output = await self._provisioner.plan(
            goal=goal,
            tools_by_server=tools_by_server,
            ctx=LLMContext(workspace_id=actor.workspace_id),
        )

        servers_by_id = {s.id: s for s in servers}
        invocations: list[ToolInvocation] = []
        for call in output.tool_calls:
            target = servers_by_id.get(call.server_id)
            if target is None or not self._governor.is_allowed(target, call.tool_name):
                logger.info("mcp.plan.dropped_call", server_id=call.server_id, tool=call.tool_name)
                continue  # governor drops unknown servers / non-allowlisted tools
            invocations.append(
                ToolInvocation(
                    id=self._id_factory(),
                    server_id=target.id,
                    tool_name=call.tool_name,
                    arguments=call.arguments,
                    rationale=call.rationale,
                    status=InvocationStatus.PROPOSED,
                )
            )

        plan = ProvisioningPlan(
            id=self._id_factory(),
            workspace_id=actor.workspace_id,
            project_id=project_id,
            goal=goal.strip(),
            summary=output.summary,
            status=PlanStatus.PROPOSED,
            created_by=actor.user_id,
            created_at=self._clock.now(),
            invocations=invocations,
        )
        await self._plans.add(plan)
        logger.info(
            "mcp.plan.created", plan_id=plan.id, calls=len(invocations), prompt=PROMPT_VERSION
        )
        return plan


class ListProvisioningPlans:
    def __init__(self, plans: ProvisioningRepository) -> None:
        self._plans = plans

    async def execute(self, actor: Actor, project_id: str) -> list[ProvisioningPlan]:
        actor.require(Permission.PROJECT_READ)
        return await self._plans.list_for_project(actor.workspace_id, project_id)


class GetProvisioningPlan:
    def __init__(self, plans: ProvisioningRepository) -> None:
        self._plans = plans

    async def execute(self, actor: Actor, plan_id: str) -> ProvisioningPlan:
        actor.require(Permission.PROJECT_READ)
        return await self._plans.get(actor.workspace_id, plan_id)


class ApproveProvisioningPlan:
    """Human approval gate: the ONLY path that executes tool calls. Runs the
    approved calls sequentially, re-checking the governor for each."""

    def __init__(
        self,
        servers: McpServerRepository,
        plans: ProvisioningRepository,
        client: McpClient,
        governor: ToolGovernor,
        audit: AuditLogger,
    ) -> None:
        self._servers = servers
        self._plans = plans
        self._client = client
        self._governor = governor
        self._audit = audit

    async def execute(self, actor: Actor, plan_id: str) -> ProvisioningPlan:
        actor.require(Permission.WORKSPACE_MANAGE)
        plan = await self._plans.get(actor.workspace_id, plan_id)
        if plan.status is not PlanStatus.PROPOSED:
            raise InvalidStateError(f"Plan is already '{plan.status}'")

        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="mcp.plan.approved",
                workspace_id=actor.workspace_id,
                target=f"plan:{plan.id}",
                metadata={"calls": len(plan.invocations)},
            )
        )

        halted = False
        for invocation in plan.invocations:
            if halted:
                invocation.status = InvocationStatus.SKIPPED
                continue
            try:
                server = await self._servers.get(actor.workspace_id, invocation.server_id)
                self._governor.authorize(server, invocation.tool_name)  # re-check at run time
                result = await self._client.invoke(
                    server, invocation.tool_name, invocation.arguments
                )
                invocation.status = InvocationStatus.SUCCEEDED
                invocation.result = result
            except Exception as exc:  # a failed call halts the sequence (doc 08 §3)
                invocation.status = InvocationStatus.FAILED
                invocation.result = {"error": str(exc)}
                halted = True

        plan.status = PlanStatus.FAILED if halted else PlanStatus.EXECUTED
        await self._plans.save(plan)
        logger.info("mcp.plan.executed", plan_id=plan.id, status=plan.status)
        return plan


class RejectProvisioningPlan:
    def __init__(self, plans: ProvisioningRepository, audit: AuditLogger) -> None:
        self._plans = plans
        self._audit = audit

    async def execute(self, actor: Actor, plan_id: str) -> ProvisioningPlan:
        actor.require(Permission.WORKSPACE_MANAGE)
        plan = await self._plans.get(actor.workspace_id, plan_id)
        if plan.status is not PlanStatus.PROPOSED:
            raise InvalidStateError(f"Plan is already '{plan.status}'")
        for invocation in plan.invocations:
            invocation.status = InvocationStatus.SKIPPED
        plan.status = PlanStatus.REJECTED
        await self._plans.save(plan)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="mcp.plan.rejected",
                workspace_id=actor.workspace_id,
                target=f"plan:{plan.id}",
            )
        )
        return plan
