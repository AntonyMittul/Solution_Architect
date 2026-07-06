"""Export a generated blueprint as a ZIP, against real Postgres with the
auto-fake LLM."""

import io
import json
import zipfile
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


async def _blueprint_ready(client: httpx.AsyncClient, container: Container) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "dan@example.com", "password": PASSWORD, "name": "Dan"},
    )
    ws = reg.json()["workspace_id"]
    await client.post("/api/v1/auth/verify", json={"token": reg.json()["verification_token"]})
    await client.post("/api/v1/auth/login", json={"email": "dan@example.com", "password": PASSWORD})
    pid = (await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "My App"})).json()[
        "id"
    ]
    posted = await client.post(
        f"/api/v1/workspaces/{ws}/projects/{pid}/messages", json={"text": "an app"}
    )
    await container.run_executors["intake"].execute(posted.json()["run_id"])
    await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/requirements/confirm")
    run_id = (await client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/blueprint")).json()[
        "run_id"
    ]
    await container.run_executors["blueprint"].execute(run_id)
    return ws, pid


async def test_export_returns_zip_bundle(container_factory: ContainerFactory) -> None:
    container = container_factory(FakeLLMProvider())
    async for client in _client_for(container):
        ws, pid = await _blueprint_ready(client, container)

        response = await client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "my-app-blueprint.zip" in response.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            assert "README.md" in names
            assert "requirements.md" in names
            assert "api/openapi.json" in names
            assert "database/schema.sql" in names
            assert "diagram/architecture.mmd" in names
            # The OpenAPI file is valid JSON.
            json.loads(archive.read("api/openapi.json"))


async def test_export_blocked_before_blueprint(container_factory: ContainerFactory) -> None:
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
        pid = (
            await client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "My App"})
        ).json()["id"]

        response = await client.get(f"/api/v1/workspaces/{ws}/projects/{pid}/export")
        assert response.status_code == 404  # no artifacts yet
