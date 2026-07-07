from aisa.integrations.domain.models import McpServer, ToolDescriptor

# A GitHub-shaped default catalog so the app is demonstrable key-less; a real
# streamable-HTTP adapter (mcp SDK) replaces this behind the McpClient port.
DEFAULT_CATALOG: list[ToolDescriptor] = [
    ToolDescriptor("create_repository", "Create a new GitHub repository"),
    ToolDescriptor("push_scaffold", "Push a project scaffold to a repository"),
    ToolDescriptor("create_issue", "Open an issue in a repository"),
    ToolDescriptor("enable_actions", "Enable GitHub Actions for a repository"),
]


class FakeMcpClient:
    """Deterministic MCP client for tests and key-less dev: a fixed tool catalog
    and echo-style invocation results."""

    def __init__(
        self,
        catalog: dict[str, list[ToolDescriptor]] | None = None,
        results: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self._catalog = catalog or {}
        self._results = results or {}
        self.invocations: list[tuple[str, str, dict[str, str]]] = []

    async def discover(self, server: McpServer) -> list[ToolDescriptor]:
        return self._catalog.get(server.name, DEFAULT_CATALOG)

    async def invoke(
        self, server: McpServer, tool_name: str, arguments: dict[str, str]
    ) -> dict[str, object]:
        self.invocations.append((server.name, tool_name, arguments))
        if tool_name in self._results:
            return self._results[tool_name]
        return {"status": "ok", "tool": tool_name, "arguments": dict(arguments)}
