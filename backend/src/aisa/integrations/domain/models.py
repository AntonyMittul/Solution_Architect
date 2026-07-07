from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class TransportKind(StrEnum):
    STREAMABLE_HTTP = "streamable_http"
    STDIO = "stdio"


class TrustLevel(StrEnum):
    UNTRUSTED = "untrusted"
    TRUSTED_READ = "trusted_read"


class ServerStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass
class McpServer:
    id: str
    workspace_id: str
    name: str
    transport: TransportKind
    endpoint: str
    trust: TrustLevel
    tool_allowlist: list[str]
    status: ServerStatus
    created_by: str
    created_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status is ServerStatus.ACTIVE

    def allows(self, tool_name: str) -> bool:
        return tool_name in self.tool_allowlist


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    description: str


class PlanStatus(StrEnum):
    PROPOSED = "proposed"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class InvocationStatus(StrEnum):
    PROPOSED = "proposed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolInvocation:
    id: str
    server_id: str
    tool_name: str
    arguments: dict[str, str]
    rationale: str
    status: InvocationStatus
    result: dict[str, object] | None = None


@dataclass
class ProvisioningPlan:
    id: str
    workspace_id: str
    project_id: str
    goal: str
    summary: str
    status: PlanStatus
    created_by: str
    created_at: datetime
    invocations: list[ToolInvocation] = field(default_factory=list)
