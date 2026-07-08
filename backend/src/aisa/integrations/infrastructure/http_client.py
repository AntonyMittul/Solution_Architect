from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Protocol

import structlog

from aisa.integrations.domain.models import McpServer, ToolDescriptor, TransportKind
from aisa.shared.errors import UnsupportedOperationError

logger = structlog.get_logger(__name__)


class _Session(Protocol):
    """Minimal surface of the mcp SDK's ClientSession we depend on."""

    async def list_tools(self) -> Any: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


Connector = Callable[[McpServer], AbstractAsyncContextManager[_Session]]


def _tools_from(result: Any) -> list[ToolDescriptor]:
    return [
        ToolDescriptor(name=tool.name, description=getattr(tool, "description", "") or "")
        for tool in getattr(result, "tools", [])
    ]


def _call_result_to_dict(result: Any) -> dict[str, object]:
    """Normalise an mcp CallToolResult into a JSON-safe dict for the audit trail."""
    out: dict[str, object] = {"is_error": bool(getattr(result, "isError", False))}
    texts = [
        block.text
        for block in getattr(result, "content", []) or []
        if getattr(block, "text", None) is not None
    ]
    if texts:
        out["content"] = texts
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        out["structured"] = structured
    return out


class HttpMcpClient:
    """Real MCP client over streamable HTTP (the `mcp` SDK). A single bearer
    token authenticates to the server (e.g. a GitHub PAT for GitHub's hosted
    MCP server). Per-workspace encrypted credentials are the multi-tenant
    upgrade; this suffices for a single connected server.

    The connector is injectable so the mapping logic is unit-testable without a
    live server."""

    def __init__(self, auth_token: str = "", connector: Connector | None = None) -> None:
        self._auth_token = auth_token
        self._connector = connector or self._default_connector

    @asynccontextmanager
    async def _default_connector(self, server: McpServer) -> AsyncIterator[_Session]:
        if server.transport is not TransportKind.STREAMABLE_HTTP:
            raise UnsupportedOperationError(
                f"HttpMcpClient supports streamable_http only, not '{server.transport}'"
            )
        # Imported here so the SDK is only needed when the real client is used.
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"Authorization": f"Bearer {self._auth_token}"} if self._auth_token else None
        async with (
            streamablehttp_client(server.endpoint, headers=headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            yield session

    async def discover(self, server: McpServer) -> list[ToolDescriptor]:
        async with self._connector(server) as session:
            tools = _tools_from(await session.list_tools())
        logger.info("mcp.discovered", server=server.name, count=len(tools))
        return tools

    async def invoke(
        self, server: McpServer, tool_name: str, arguments: Mapping[str, str]
    ) -> dict[str, object]:
        async with self._connector(server) as session:
            result = _call_result_to_dict(await session.call_tool(tool_name, dict(arguments)))
        logger.info("mcp.invoked", server=server.name, tool=tool_name, is_error=result["is_error"])
        return result
