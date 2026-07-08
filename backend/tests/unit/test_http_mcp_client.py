from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from aisa.integrations.domain.models import (
    McpServer,
    ServerStatus,
    TransportKind,
    TrustLevel,
)
from aisa.integrations.infrastructure.http_client import (
    HttpMcpClient,
    _call_result_to_dict,
    _tools_from,
)
from aisa.shared.errors import UnsupportedOperationError

NOW = datetime(2026, 7, 7, tzinfo=UTC)


def server(transport: TransportKind = TransportKind.STREAMABLE_HTTP) -> McpServer:
    return McpServer(
        id="s1",
        workspace_id="w1",
        name="github",
        transport=transport,
        endpoint="https://mcp.example/github",
        trust=TrustLevel.UNTRUSTED,
        tool_allowlist=["create_repository"],
        status=ServerStatus.ACTIVE,
        created_by="u1",
        created_at=NOW,
    )


@dataclass
class _Tool:
    name: str
    description: str | None


@dataclass
class _Text:
    text: str


class _FakeSession:
    def __init__(self) -> None:
        self.called: tuple[str, dict[str, Any]] | None = None

    async def list_tools(self) -> Any:
        return type(
            "R",
            (),
            {"tools": [_Tool("create_repository", "Create a repo"), _Tool("create_issue", None)]},
        )()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.called = (name, arguments)
        return type(
            "CR",
            (),
            {
                "isError": False,
                "content": [_Text("created")],
                "structuredContent": {"url": "https://github.com/x/y"},
            },
        )()


def _connector(session: _FakeSession):  # type: ignore[no-untyped-def]
    @asynccontextmanager
    async def connect(_server: McpServer) -> AsyncIterator[_FakeSession]:
        yield session

    return connect


def test_tools_from_maps_names_and_missing_descriptions() -> None:
    result = type("R", (), {"tools": [_Tool("a", None), _Tool("b", "desc")]})()
    tools = _tools_from(result)
    assert [(t.name, t.description) for t in tools] == [("a", ""), ("b", "desc")]


def test_call_result_to_dict_extracts_text_and_structured() -> None:
    result = type(
        "CR",
        (),
        {"isError": True, "content": [_Text("oops")], "structuredContent": {"k": 1}},
    )()
    assert _call_result_to_dict(result) == {
        "is_error": True,
        "content": ["oops"],
        "structured": {"k": 1},
    }


async def test_discover_uses_the_session() -> None:
    session = _FakeSession()
    client = HttpMcpClient(auth_token="t", connector=_connector(session))
    tools = await client.discover(server())
    assert {t.name for t in tools} == {"create_repository", "create_issue"}


async def test_invoke_passes_arguments_and_normalises_result() -> None:
    session = _FakeSession()
    client = HttpMcpClient(connector=_connector(session))
    result = await client.invoke(server(), "create_repository", {"name": "food-app"})
    assert session.called == ("create_repository", {"name": "food-app"})
    assert result["is_error"] is False
    assert result["structured"] == {"url": "https://github.com/x/y"}


async def test_default_connector_rejects_stdio() -> None:
    client = HttpMcpClient(auth_token="t")  # real connector
    with pytest.raises(UnsupportedOperationError):
        await client.discover(server(transport=TransportKind.STDIO))
