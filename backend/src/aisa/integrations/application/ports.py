from typing import Protocol

from aisa.integrations.domain.models import McpServer, ProvisioningPlan, ToolDescriptor


class McpServerRepository(Protocol):
    async def add(self, server: McpServer) -> None: ...

    async def get(self, workspace_id: str, server_id: str) -> McpServer:
        """Raises NotFoundError."""
        ...

    async def list_all(self, workspace_id: str) -> list[McpServer]: ...

    async def list_active(self, workspace_id: str) -> list[McpServer]: ...

    async def save(self, server: McpServer) -> None: ...

    async def remove(self, workspace_id: str, server_id: str) -> None: ...


class ProvisioningRepository(Protocol):
    async def add(self, plan: ProvisioningPlan) -> None: ...

    async def get(self, workspace_id: str, plan_id: str) -> ProvisioningPlan:
        """Raises NotFoundError."""
        ...

    async def list_for_project(
        self, workspace_id: str, project_id: str
    ) -> list[ProvisioningPlan]: ...

    async def save(self, plan: ProvisioningPlan) -> None: ...


class McpClient(Protocol):
    """Talks to an MCP server. The fake implementation backs tests and key-less
    dev; a real streamable-HTTP adapter (mcp SDK) is a drop-in replacement."""

    async def discover(self, server: McpServer) -> list[ToolDescriptor]: ...

    async def invoke(
        self, server: McpServer, tool_name: str, arguments: dict[str, str]
    ) -> dict[str, object]: ...
