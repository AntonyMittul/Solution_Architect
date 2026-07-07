from datetime import UTC, datetime

import pytest

from aisa.integrations.application.agent import Provisioner
from aisa.integrations.application.governor import ToolGovernor
from aisa.integrations.domain.models import (
    McpServer,
    ServerStatus,
    ToolDescriptor,
    TransportKind,
    TrustLevel,
)
from aisa.integrations.domain.schemas import ProvisioningPlanOutput
from aisa.llm.application.service import LLMContext, StructuredLLM
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.llm.infrastructure.usage import NullUsageRecorder
from aisa.shared.errors import DomainValidationError

NOW = datetime(2026, 7, 7, tzinfo=UTC)


def server(*, allowlist: list[str], status: ServerStatus = ServerStatus.ACTIVE) -> McpServer:
    return McpServer(
        id="srv1",
        workspace_id="w1",
        name="github",
        transport=TransportKind.STREAMABLE_HTTP,
        endpoint="https://mcp.example",
        trust=TrustLevel.UNTRUSTED,
        tool_allowlist=allowlist,
        status=status,
        created_by="u1",
        created_at=NOW,
    )


def test_governor_allows_only_allowlisted_active() -> None:
    governor = ToolGovernor()
    srv = server(allowlist=["create_repository"])
    governor.authorize(srv, "create_repository")  # no raise
    assert governor.is_allowed(srv, "create_repository") is True
    assert governor.is_allowed(srv, "delete_everything") is False


def test_governor_rejects_non_allowlisted_tool() -> None:
    governor = ToolGovernor()
    with pytest.raises(DomainValidationError):
        governor.authorize(server(allowlist=["create_repository"]), "create_issue")


def test_governor_rejects_disabled_server() -> None:
    governor = ToolGovernor()
    srv = server(allowlist=["create_repository"], status=ServerStatus.DISABLED)
    assert governor.is_allowed(srv, "create_repository") is False
    with pytest.raises(DomainValidationError):
        governor.authorize(srv, "create_repository")


async def test_provisioner_produces_plan_from_catalog() -> None:
    plan_json = ProvisioningPlanOutput(
        summary="Create the repo and open a setup issue.",
        tool_calls=[
            {
                "server_id": "srv1",
                "tool_name": "create_repository",
                "arguments": {"name": "my-app"},
                "rationale": "root of the project",
            }
        ],
    ).model_dump_json()
    provider = FakeLLMProvider(responses=[plan_json])
    provisioner = Provisioner(StructuredLLM(provider, NullUsageRecorder()))

    output = await provisioner.plan(
        goal="Scaffold a repo for my app",
        tools_by_server={
            "srv1": (
                server(allowlist=["create_repository"]),
                [ToolDescriptor("create_repository", "…")],
            )
        },
        ctx=LLMContext(workspace_id="w1"),
    )

    assert output.tool_calls[0].tool_name == "create_repository"
    # The catalog (server_id + tool) reached the model's system prompt.
    system, _ = provider.calls[0]
    assert "srv1" in system and "create_repository" in system
