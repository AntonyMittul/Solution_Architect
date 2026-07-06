"""End-to-end blueprint generation against real Postgres with the auto-fake LLM.
The executor is driven directly to stand in for the worker."""

from collections.abc import AsyncIterator

import httpx

from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.platform.app import create_app
from aisa.platform.container import Container
from tests.component.conftest import ContainerFactory

PASSWORD = "correct-horse-battery"
ALL_TYPES = {
    "architecture_doc",
    "tech_stack",
    "api_spec",
    "db_schema",
    "diagram",
    "cost_estimate",
    "design_doc",
}


async def _client_for(container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(container))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _project_with_confirmed_requirements(
    client: httpx.AsyncClient, container: Container
) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "dan@example.com", "password": PASSWORD, "name": "Dan"},
    )
    ws = reg.json()["workspace_id"]
    await client.post("/api/v1/auth/verify", json={"token": reg.json()["verification_token"]})
    await client.post("/api/v1/auth/login", json={"email": "dan@example.com", "password": PASSWORD})
    pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "App"})).json()[
        "id"
    ]

    posted = await client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/messages",
        json={"text": "Build a food delivery app for a million users"},
    )
    await container.run_executors["intake"].execute(posted.json()["run_id"])
    await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/requirements/confirm")
    return ws, pid


async def test_blueprint_generates_all_artifacts(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider())  # auto schema-valid output
    async for client in _client_for(container):
        ws, pid = await _project_with_confirmed_requirements(client, container)

        started = await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/blueprint")
        assert started.status_code == 201, started.text
        run_id = started.json()["run_id"]

        await container.run_executors["blueprint"].execute(run_id)

        assert (await client.get(f"/api/v1/runs/{run_id}")).json()["status"] == "completed"

        artifacts = (await client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/artifacts")).json()
        assert {a["type"] for a in artifacts} == ALL_TYPES
        for artifact in artifacts:
            assert artifact["latest"] is not None
            assert artifact["latest"]["version"] == 1
            prov = artifact["latest"]["provenance"]
            assert prov["run_id"] == run_id
            assert prov["source"] == "agent"
            assert prov["requirements_version"] == 1

        # A specific artifact + its version history is retrievable.
        diagram = await client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/artifacts/diagram")
        assert diagram.status_code == 200
        versions = await client.get(
            f"/api/v1/workspaces/{ws}/projects/{pid}/artifacts/design_doc/versions"
        )
        assert len(versions.json()) == 1


async def test_blueprint_blocked_without_confirmed_requirements(
    container_factory: ContainerFactory,
) -> None:
    container = container_factory(FakeLLMProvider())
    async for client in _client_for(container):
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": "dan@example.com", "password": PASSWORD, "name": "Dan"},
        )
        ws = reg.json()["workspace_id"]
        await client.post("/api/v1/auth/verify", json={"token": reg.json()["verification_token"]})
        await client.post(
            "/api/v1/auth/login", json={"email": "dan@example.com", "password": PASSWORD}
        )
        pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "App"})).json()[
            "id"
        ]

        # No requirements at all -> blocked.
        blocked = await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/blueprint")
        assert blocked.status_code == 409

        # Draft (unconfirmed) requirements -> still blocked.
        posted = await client.post(
            f"/api/v1/workspaces/{ws}/projects/{pid}/messages", json={"text": "an app"}
        )
        await container.run_executors["intake"].execute(posted.json()["run_id"])
        still_blocked = await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/blueprint")
        assert still_blocked.status_code == 409

        await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/requirements/confirm")
        allowed = await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/blueprint")
        assert allowed.status_code == 201


async def test_second_blueprint_run_appends_versions(
    container_factory: ContainerFactory,
) -> None:
    container = container_factory(FakeLLMProvider())
    async for client in _client_for(container):
        ws, pid = await _project_with_confirmed_requirements(client, container)

        for _ in range(2):
            run_id = (
                await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/blueprint")
            ).json()["run_id"]
            await container.run_executors["blueprint"].execute(run_id)

        versions = await client.get(
            f"/api/v1/workspaces/{ws}/projects/{pid}/artifacts/architecture_doc/versions"
        )
        assert [v["version"] for v in versions.json()] == [2, 1]
