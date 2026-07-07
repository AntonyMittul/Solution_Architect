"""MCP provisioning end to end against real Postgres with the fake MCP client:
plan -> governed approval -> execution, plus the safety properties."""

import re
from collections.abc import AsyncIterator

import httpx

from aisa.integrations.domain.schemas import PlannedToolCall, ProvisioningPlanOutput
from aisa.llm.domain.messages import LLMMessage
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.platform.app import create_app
from aisa.platform.container import Container
from tests.component.conftest import ContainerFactory

PASSWORD = "correct-horse-battery"
SERVER = {
    "name": "github",
    "transport": "streamable_http",
    "endpoint": "https://mcp.example",
    "trust": "untrusted",
    "tool_allowlist": ["create_repository", "create_issue"],
}


def plan_handler(system: str, messages: list[LLMMessage], model: type) -> str:
    # The catalog in the system prompt carries the real server id; reference it,
    # and also propose a NON-allowlisted tool that the governor must drop.
    match = re.search(r"server_id=(\w+)", system)
    server_id = match.group(1) if match else "unknown"
    return ProvisioningPlanOutput(
        summary="Create the repository, then push a scaffold.",
        tool_calls=[
            PlannedToolCall(
                server_id=server_id,
                tool_name="create_repository",
                arguments={"name": "my-app", "private": "true"},
                rationale="root of the project",
            ),
            PlannedToolCall(
                server_id=server_id,
                tool_name="delete_everything",  # not allowlisted -> dropped
                arguments={},
                rationale="should never survive the governor",
            ),
        ],
    ).model_dump_json()


async def _client_for(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(container))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _verified_owner(client: httpx.AsyncClient, email: str = "dan@example.com") -> str:
    reg = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "name": "Dan"}
    )
    ws = reg.json()["workspace_id"]
    await client.post("/api/v1/auth/verify", json={"token": reg.json()["verification_token"]})
    await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return ws


async def test_provisioning_plan_approve_executes(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider(handler=plan_handler))
    async for client in _client_for(container):
        ws = await _verified_owner(client)

        srv = await client.post(f"/api/v1/workspaces/{ws}/mcp-servers", json=SERVER)
        assert srv.status_code == 201, srv.text

        tools = await client.get(f"/api/v1/workspaces/{ws}/mcp-servers/{srv.json()['id']}/tools")
        assert "create_repository" in [t["name"] for t in tools.json()]

        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P"})).json()[
            "id"
        ]
        base = f"/api/v1/workspaces/{ws}/projects/{pid}/provisioning"

        created = await client.post(f"{base}/plans", json={"goal": "scaffold a repo"})
        assert created.status_code == 201, created.text
        plan = created.json()
        assert plan["status"] == "proposed"
        # Governor dropped the non-allowlisted call; nothing executed yet.
        assert [i["tool_name"] for i in plan["invocations"]] == ["create_repository"]
        assert all(i["status"] == "proposed" for i in plan["invocations"])

        approved = await client.post(f"{base}/plans/{plan['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "executed"
        invocation = approved.json()["invocations"][0]
        assert invocation["status"] == "succeeded"
        assert invocation["result"]["status"] == "ok"

        # Re-approving an already-executed plan is a conflict.
        assert (await client.post(f"{base}/plans/{plan['id']}/approve")).status_code == 409


async def test_provisioning_plan_reject(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider(handler=plan_handler))
    async for client in _client_for(container):
        ws = await _verified_owner(client)
        await client.post(f"/api/v1/workspaces/{ws}/mcp-servers", json=SERVER)
        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P"})).json()[
            "id"
        ]
        base = f"/api/v1/workspaces/{ws}/projects/{pid}/provisioning"
        plan_id = (await client.post(f"{base}/plans", json={"goal": "x"})).json()["id"]

        rejected = await client.post(f"{base}/plans/{plan_id}/reject")
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert all(i["status"] == "skipped" for i in rejected.json()["invocations"])


async def test_provisioning_requires_a_server(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider(handler=plan_handler))
    async for client in _client_for(container):
        ws = await _verified_owner(client)
        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P"})).json()[
            "id"
        ]
        # No MCP server registered yet.
        resp = await client.post(
            f"/api/v1/workspaces/{ws}/projects/{pid}/provisioning/plans", json={"goal": "x"}
        )
        assert resp.status_code == 404


async def test_member_cannot_manage_servers(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider())
    async for client in _client_for(container):
        await _verified_owner(client, "owner@example.com")
        ws = (await client.post("/api/v1/workspaces", json={"name": "Acme"})).json()["id"]

        member = httpx.AsyncClient(transport=client._transport, base_url="http://test")
        async with member:
            await _verified_owner(member, "sam@example.com")
            await client.post(
                f"/api/v1/workspaces/{ws}/members",
                json={"email": "sam@example.com", "role": "member"},
            )
            await member.post(
                "/api/v1/auth/login", json={"email": "sam@example.com", "password": PASSWORD}
            )
            # WORKSPACE_MANAGE required to register an MCP server.
            denied = await member.post(f"/api/v1/workspaces/{ws}/mcp-servers", json=SERVER)
            assert denied.status_code == 403
