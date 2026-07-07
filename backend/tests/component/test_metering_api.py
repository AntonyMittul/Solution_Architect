"""Usage dashboard + monthly run-quota enforcement against real Postgres."""

from collections.abc import AsyncIterator

import httpx

from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.platform.app import create_app
from aisa.platform.container import Container
from tests.component.conftest import ContainerFactory

PASSWORD = "correct-horse-battery"


async def _client_for(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(container))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _verified_owner(client: httpx.AsyncClient) -> str:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "dan@example.com", "password": PASSWORD, "name": "Dan"},
    )
    ws = reg.json()["workspace_id"]
    await client.post("/api/v1/auth/verify", json={"token": reg.json()["verification_token"]})
    await client.post("/api/v1/auth/login", json={"email": "dan@example.com", "password": PASSWORD})
    return ws


async def test_usage_endpoint_reflects_activity(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider())
    async for client in _client_for(container):
        ws = await _verified_owner(client)

        before = await client.get(f"/api/v1/workspaces/{ws}/usage")
        assert before.status_code == 200
        assert before.json()["plan"] == "free"
        assert before.json()["runs_this_month"] == 0

        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "App"})).json()[
            "id"
        ]
        posted = await client.post(
            f"/api/v1/workspaces/{ws}/projects/{pid}/messages", json={"text": "an app"}
        )
        await container.run_executors["intake"].execute(posted.json()["run_id"])

        after = (await client.get(f"/api/v1/workspaces/{ws}/usage")).json()
        assert after["runs_this_month"] == 1
        assert after["total_tokens"] > 0  # the intake run recorded token usage
        assert after["monthly_run_quota"] >= 1


async def test_run_quota_blocks_new_runs(container_factory: ContainerFactory) -> None:
    # A tiny quota so the second run is rejected.
    container = container_factory(FakeLLMProvider(), free_monthly_run_quota=1)
    async for client in _client_for(container):
        ws = await _verified_owner(client)
        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "App"})).json()[
            "id"
        ]
        url = f"/api/v1/workspaces/{ws}/projects/{pid}/messages"

        first = await client.post(url, json={"text": "idea one"})
        assert first.status_code == 201  # consumes the 1-run quota

        blocked = await client.post(url, json={"text": "idea two"})
        assert blocked.status_code == 429
        assert blocked.headers["content-type"] == "application/problem+json"
        assert "run limit" in blocked.json()["detail"].lower()


async def test_token_budget_fails_run(container_factory: ContainerFactory) -> None:
    # A tiny per-run budget: the first analyst call (30 fake tokens) exceeds it,
    # so the run stops gracefully and is marked failed.
    container = container_factory(FakeLLMProvider(), free_run_token_budget=10)
    async for client in _client_for(container):
        ws = await _verified_owner(client)
        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "App"})).json()[
            "id"
        ]
        posted = await client.post(
            f"/api/v1/workspaces/{ws}/projects/{pid}/messages", json={"text": "an app"}
        )
        run_id = posted.json()["run_id"]

        await container.run_executors["intake"].execute(run_id)

        run = (await client.get(f"/api/v1/runs/{run_id}")).json()
        assert run["status"] == "failed"
        assert "budget" in (run["error"] or "").lower()


async def test_usage_requires_membership(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider())
    async for client in _client_for(container):
        ws = await _verified_owner(client)
        outsider = httpx.AsyncClient(transport=client._transport, base_url="http://test")
        async with outsider:
            reg = await outsider.post(
                "/api/v1/auth/register",
                json={"email": "mallory@example.com", "password": PASSWORD, "name": "M"},
            )
            await outsider.post(
                "/api/v1/auth/verify", json={"token": reg.json()["verification_token"]}
            )
            await outsider.post(
                "/api/v1/auth/login", json={"email": "mallory@example.com", "password": PASSWORD}
            )
            assert (await outsider.get(f"/api/v1/workspaces/{ws}/usage")).status_code == 404
