from aisa.integrations.domain.models import McpServer
from aisa.shared.errors import DomainValidationError

# The governor is the single choke point every tool call passes through
# (doc 08 §2). It is enforced structurally at both plan creation and execution,
# so a prompt-injected agent can at most *propose* a disallowed call.


class ToolGovernor:
    def authorize(self, server: McpServer, tool_name: str) -> None:
        if not server.is_active:
            raise DomainValidationError(f"MCP server '{server.name}' is disabled")
        if not server.allows(tool_name):
            raise DomainValidationError(
                f"Tool '{tool_name}' is not allowlisted on server '{server.name}'"
            )

    def is_allowed(self, server: McpServer, tool_name: str) -> bool:
        return server.is_active and server.allows(tool_name)
