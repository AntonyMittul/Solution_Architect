from aisa.integrations.domain.models import McpServer, ToolDescriptor
from aisa.integrations.domain.schemas import ProvisioningPlanOutput
from aisa.llm.application.service import LLMContext, StructuredLLM
from aisa.llm.domain.messages import LLMMessage, MessageRole, ModelTier

PROMPT_VERSION = "provisioner_v1"

_SYSTEM = """You are the Provisioner, an agent that turns a provisioning goal into
an ORDERED PLAN of tool calls against pre-approved MCP servers. You never execute
anything — you only propose a plan that a human will review and approve.

Rules:
- Use ONLY the tools in the catalog below, referencing them by their exact
  `server_id` and `tool_name`. Never invent a server or a tool.
- Order the calls so dependencies come first (e.g. create a repository before
  opening issues in it).
- Provide concrete `arguments` (all string values) and a short `rationale` per call.
- If the goal cannot be met with the available tools, return an empty `tool_calls`
  list and explain why in `summary`.

Available tool catalog:
{catalog}
"""


def _render_catalog(tools_by_server: dict[str, tuple[McpServer, list[ToolDescriptor]]]) -> str:
    lines: list[str] = []
    for server, tools in tools_by_server.values():
        lines.append(f"- server_id={server.id} ({server.name}):")
        for tool in tools:
            lines.append(f"    - {tool.name}: {tool.description}")
    return "\n".join(lines) if lines else "(no tools available)"


class Provisioner:
    """A thin typed agent (over the LLM port) that plans MCP tool calls."""

    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm

    async def plan(
        self,
        *,
        goal: str,
        tools_by_server: dict[str, tuple[McpServer, list[ToolDescriptor]]],
        ctx: LLMContext,
    ) -> ProvisioningPlanOutput:
        system = _SYSTEM.format(catalog=_render_catalog(tools_by_server))
        return await self._llm.complete(
            system=system,
            messages=[LLMMessage(MessageRole.USER, goal)],
            schema=ProvisioningPlanOutput,
            ctx=ctx,
            tier=ModelTier.QUALITY,
        )
