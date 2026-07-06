"""End-to-end identity + projects flows against real Postgres (RLS active:
the app connects as the non-bypass aisa_app role)."""

import httpx

PASSWORD = "correct-horse-battery"


async def register(client: httpx.AsyncClient, email: str, name: str = "Test User") -> dict:
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login(client: httpx.AsyncClient, email: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


async def register_verified(client: httpx.AsyncClient, email: str, name: str = "User") -> dict:
    result = await register(client, email, name)
    verify = await client.post("/api/v1/auth/verify", json={"token": result["verification_token"]})
    assert verify.status_code == 200, verify.text
    return result


async def test_register_login_me(db_client: httpx.AsyncClient) -> None:
    result = await register(db_client, "dan@example.com", "Dev Dan")
    assert result["user"]["email_verified"] is False
    assert result["verification_token"]  # dev mode exposes it
    await login(db_client, "dan@example.com")

    me = await db_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "dan@example.com"

    workspaces = await db_client.get("/api/v1/workspaces")
    assert [w["kind"] for w in workspaces.json()] == ["personal"]
    assert workspaces.json()[0]["role"] == "owner"


async def test_wrong_password_and_duplicate_email(db_client: httpx.AsyncClient) -> None:
    await register(db_client, "dan@example.com")
    bad = await db_client.post(
        "/api/v1/auth/login", json={"email": "dan@example.com", "password": "wrong-password-1"}
    )
    assert bad.status_code == 401
    dup = await db_client.post(
        "/api/v1/auth/register",
        json={"email": "dan@example.com", "password": PASSWORD, "name": "X"},
    )
    assert dup.status_code == 409


async def test_unverified_email_blocks_project_creation(db_client: httpx.AsyncClient) -> None:
    result = await register(db_client, "dan@example.com")
    ws = result["workspace_id"]
    await login(db_client, "dan@example.com")

    denied = await db_client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "App"})
    assert denied.status_code == 403

    verified = await db_client.post(
        "/api/v1/auth/verify", json={"token": result["verification_token"]}
    )
    assert verified.status_code == 200
    created = await db_client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "App"})
    assert created.status_code == 201, created.text


async def test_project_crud_soft_delete_restore(db_client: httpx.AsyncClient) -> None:
    result = await register_verified(db_client, "dan@example.com")
    ws = result["workspace_id"]
    await login(db_client, "dan@example.com")

    project = (
        await db_client.post(
            f"/api/v1/workspaces/{ws}/projects",
            json={"name": "Food app", "settings": {"target_cloud": "aws"}},
        )
    ).json()
    pid = project["id"]

    patched = await db_client.patch(
        f"/api/v1/workspaces/{ws}/projects/{pid}", json={"name": "Food delivery app"}
    )
    assert patched.json()["name"] == "Food delivery app"

    assert (await db_client.delete(f"/api/v1/workspaces/{ws}/projects/{pid}")).status_code == 204
    assert (await db_client.get(f"/api/v1/workspaces/{ws}/projects/{pid}")).status_code == 404
    assert (await db_client.get(f"/api/v1/workspaces/{ws}/projects")).json() == []

    restored = await db_client.post(f"/api/v1/workspaces/{ws}/projects/{pid}/restore")
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None
    assert (await db_client.get(f"/api/v1/workspaces/{ws}/projects/{pid}")).status_code == 200


async def test_rbac_matrix_through_api(db_client: httpx.AsyncClient) -> None:
    # Owner sets up a team workspace with one project.
    await register_verified(db_client, "owner@example.com", "Owner")
    await login(db_client, "owner@example.com")
    team = (await db_client.post("/api/v1/workspaces", json={"name": "Acme"})).json()
    ws = team["id"]
    await db_client.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "P1"})

    # Second user joins as viewer.
    other = httpx.AsyncClient(
        transport=db_client._transport,
        base_url="http://test",  # same app, own cookie jar
    )
    async with other:
        await register_verified(other, "sam@example.com", "Sam")
        invited = await db_client.post(
            f"/api/v1/workspaces/{ws}/members", json={"email": "sam@example.com", "role": "viewer"}
        )
        assert invited.status_code == 201
        await login(other, "sam@example.com")

        # viewer: read yes, write no, member-manage no
        assert (await other.get(f"/api/v1/workspaces/{ws}/projects")).status_code == 200
        assert (
            await other.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "X"})
        ).status_code == 403
        assert (
            await other.post(
                f"/api/v1/workspaces/{ws}/members",
                json={"email": "owner@example.com", "role": "viewer"},
            )
        ).status_code == 403

        # promoted to member: write yes, member-manage still no
        promote = await db_client.patch(
            f"/api/v1/workspaces/{ws}/members/{invited.json()['user_id']}",
            json={"role": "member"},
        )
        assert promote.status_code == 200
        assert (
            await other.post(f"/api/v1/workspaces/{ws}/projects", json={"name": "By Sam"})
        ).status_code == 201

        # owner protections
        owner_id = next(
            m["user_id"]
            for m in (await db_client.get(f"/api/v1/workspaces/{ws}/members")).json()
            if m["role"] == "owner"
        )
        assert (
            await db_client.patch(
                f"/api/v1/workspaces/{ws}/members/{owner_id}", json={"role": "viewer"}
            )
        ).status_code == 409
        assert (
            await db_client.delete(f"/api/v1/workspaces/{ws}/members/{owner_id}")
        ).status_code == 409


async def test_non_member_gets_404_not_403(db_client: httpx.AsyncClient) -> None:
    await register_verified(db_client, "owner@example.com")
    await login(db_client, "owner@example.com")
    ws = (await db_client.post("/api/v1/workspaces", json={"name": "Secret"})).json()["id"]

    outsider = httpx.AsyncClient(transport=db_client._transport, base_url="http://test")
    async with outsider:
        await register_verified(outsider, "mallory@example.com")
        await login(outsider, "mallory@example.com")
        # Workspace existence is not revealed to outsiders.
        assert (await outsider.get(f"/api/v1/workspaces/{ws}/projects")).status_code == 404
        assert (await outsider.get(f"/api/v1/workspaces/{ws}/members")).status_code == 404


async def test_personal_workspace_cannot_invite(db_client: httpx.AsyncClient) -> None:
    result = await register_verified(db_client, "dan@example.com")
    await login(db_client, "dan@example.com")
    other = httpx.AsyncClient(transport=db_client._transport, base_url="http://test")
    async with other:
        await register(other, "sam@example.com")
        response = await db_client.post(
            f"/api/v1/workspaces/{result['workspace_id']}/members",
            json={"email": "sam@example.com", "role": "member"},
        )
        assert response.status_code == 409


async def test_refresh_rotation_and_reuse_detection(db_client: httpx.AsyncClient) -> None:
    await register_verified(db_client, "dan@example.com")
    await login(db_client, "dan@example.com")
    first_refresh = db_client.cookies.get("aisa_refresh")
    assert first_refresh

    rotated = await db_client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    second_refresh = db_client.cookies.get("aisa_refresh")
    assert second_refresh and second_refresh != first_refresh

    async def refresh_with(token: str) -> int:
        # Fresh client per attempt: no jar interference from server-set cookies.
        client = httpx.AsyncClient(transport=db_client._transport, base_url="http://test")
        async with client:
            client.cookies.set("aisa_refresh", token, domain="test", path="/api/v1/auth")
            return (await client.post("/api/v1/auth/refresh")).status_code

    # Replay the old token: rejected, and the whole family is revoked with it.
    assert await refresh_with(first_refresh) == 401
    assert await refresh_with(second_refresh) == 401


async def test_requests_without_auth_are_401(db_client: httpx.AsyncClient) -> None:
    assert (await db_client.get("/api/v1/auth/me")).status_code == 401
    assert (await db_client.get("/api/v1/workspaces")).status_code == 401
