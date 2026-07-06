"""Row-level security cross-tenant suite (permanent merge blocker, doc 12 §2).

Connects as the non-bypass `aisa_app` role and proves that Postgres itself
refuses cross-tenant reads and writes on `projects`, independent of any
application-layer filtering.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.component.conftest import ADMIN_URL, APP_URL

NOW = datetime(2026, 7, 6, tzinfo=UTC)


@pytest.fixture
async def seeded_engines(test_database: str) -> AsyncIterator[tuple[AsyncEngine, AsyncEngine]]:
    admin = create_async_engine(ADMIN_URL)
    app = create_async_engine(APP_URL)
    async with admin.begin() as conn:
        await conn.execute(
            text("TRUNCATE artifacts, requirement_docs, projects, workspaces CASCADE")
        )
        for ws, project in (("wsA", "projA"), ("wsB", "projB")):
            await conn.execute(
                text(
                    "INSERT INTO workspaces (id, slug, name, kind, plan, region, settings,"
                    " created_at, updated_at) VALUES (:id, :slug, :name, 'team', 'free', 'us',"
                    " '{}', :now, :now)"
                ),
                {"id": ws, "slug": ws, "name": ws, "now": NOW},
            )
            await conn.execute(
                text(
                    "INSERT INTO projects (id, workspace_id, name, status, settings,"
                    " created_by, created_at, updated_at) VALUES"
                    " (:id, :ws, :name, 'active', '{}', 'u1', :now, :now)"
                ),
                {"id": project, "ws": ws, "name": project, "now": NOW},
            )
            await conn.execute(
                text(
                    "INSERT INTO requirement_docs (id, workspace_id, project_id, version,"
                    " status, content, created_by, created_at) VALUES"
                    " (:id, :ws, :proj, 1, 'draft', '{}', 'agent', :now)"
                ),
                {"id": f"req{ws}", "ws": ws, "proj": project, "now": NOW},
            )
            await conn.execute(
                text(
                    "INSERT INTO artifacts (id, workspace_id, project_id, type, is_stale)"
                    " VALUES (:id, :ws, :proj, 'diagram', false)"
                ),
                {"id": f"art{ws}", "ws": ws, "proj": project},
            )
    yield admin, app
    await app.dispose()
    await admin.dispose()


async def _visible_projects(app: AsyncEngine, workspace_id: str | None) -> list[str]:
    async with app.connect() as conn:
        if workspace_id is not None:
            await conn.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": workspace_id}
            )
        rows = await conn.execute(text("SELECT id FROM projects ORDER BY id"))
        return [row[0] for row in rows]


async def test_rls_filters_reads_to_the_set_tenant(
    seeded_engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    _, app = seeded_engines
    assert await _visible_projects(app, "wsA") == ["projA"]
    assert await _visible_projects(app, "wsB") == ["projB"]


async def test_rls_returns_nothing_without_tenant_context(
    seeded_engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    _, app = seeded_engines
    assert await _visible_projects(app, None) == []


async def test_rls_blocks_cross_tenant_insert(
    seeded_engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    _, app = seeded_engines
    with pytest.raises(DBAPIError):
        async with app.begin() as conn:
            await conn.execute(text("SELECT set_config('app.workspace_id', 'wsA', true)"))
            # Claims to be in wsA but writes a wsB row: policy WITH CHECK fails.
            await conn.execute(
                text(
                    "INSERT INTO projects (id, workspace_id, name, status, settings,"
                    " created_by, created_at, updated_at) VALUES"
                    " ('evil', 'wsB', 'evil', 'active', '{}', 'u1', :now, :now)"
                ),
                {"now": NOW},
            )


async def test_rls_filters_requirement_docs_per_tenant(
    seeded_engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    _, app = seeded_engines
    for workspace_id, expected in (("wsA", ["reqwsA"]), ("wsB", ["reqwsB"])):
        async with app.connect() as conn:
            await conn.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": workspace_id}
            )
            rows = await conn.execute(text("SELECT id FROM requirement_docs ORDER BY id"))
            assert [row[0] for row in rows] == expected


async def test_rls_filters_artifacts_per_tenant(
    seeded_engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    _, app = seeded_engines
    for workspace_id, expected in (("wsA", ["artwsA"]), ("wsB", ["artwsB"])):
        async with app.connect() as conn:
            await conn.execute(
                text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": workspace_id}
            )
            rows = await conn.execute(text("SELECT id FROM artifacts ORDER BY id"))
            assert [row[0] for row in rows] == expected


async def test_rls_makes_cross_tenant_update_a_noop(
    seeded_engines: tuple[AsyncEngine, AsyncEngine],
) -> None:
    admin, app = seeded_engines
    async with app.begin() as conn:
        await conn.execute(text("SELECT set_config('app.workspace_id', 'wsA', true)"))
        result = await conn.execute(text("UPDATE projects SET name = 'pwned' WHERE id = 'projB'"))
        assert result.rowcount == 0  # row invisible -> nothing updated

    async with admin.connect() as conn:  # admin sees the truth
        name = await conn.scalar(text("SELECT name FROM projects WHERE id = 'projB'"))
        assert name == "projB"
