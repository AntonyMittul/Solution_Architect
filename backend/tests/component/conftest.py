"""Fixtures for component tests that need real Postgres.

A dedicated `aisa_test` database is (re)created once per session and migrated
with Alembic; each test truncates all tables. Tests are skipped cleanly when
Postgres is not reachable (unit tests never need it).
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from aisa.llm.application.ports import LLMProvider
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.platform.app import create_app
from aisa.platform.container import Container
from aisa.shared.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
PG_HOST = os.environ.get("AISA_TEST_PG_HOST", "localhost")
PG_PORT = os.environ.get("AISA_TEST_PG_PORT", "5432")
TEST_DB = "aisa_test"

ADMIN_URL = f"postgresql+asyncpg://aisa:aisa@{PG_HOST}:{PG_PORT}/{TEST_DB}"
APP_URL = f"postgresql+asyncpg://aisa_app:aisa_app@{PG_HOST}:{PG_PORT}/{TEST_DB}"

ALL_TABLES = (
    "llm_usage, requirement_docs, messages, threads, "
    "audit_log, projects, email_verification_tokens, refresh_tokens, "
    "agent_events, runs, memberships, workspaces, users"
)


async def _recreate_database() -> None:
    import asyncpg

    conn = await asyncpg.connect(
        user="aisa", password="aisa", host=PG_HOST, port=int(PG_PORT), database="postgres"
    )
    try:
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        await conn.execute(f"CREATE DATABASE {TEST_DB}")
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def test_database() -> str:
    """Recreate + migrate the test database; returns the app-role URL."""
    try:
        asyncio.run(_recreate_database())
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Postgres not available for component tests: {exc}")
    env = os.environ.copy()
    env["AISA_DATABASE_ADMIN_URL"] = ADMIN_URL
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade failed:\n{result.stdout}\n{result.stderr}")
    return APP_URL


ContainerFactory = Callable[[LLMProvider | None], Container]


@pytest.fixture
async def container_factory(test_database: str) -> AsyncIterator[ContainerFactory]:
    # Truncate as admin (bypasses RLS) so every test starts clean.
    admin_engine = create_async_engine(ADMIN_URL)
    async with admin_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {ALL_TABLES} CASCADE"))
    await admin_engine.dispose()

    built: list[Container] = []

    def make(llm_provider: LLMProvider | None = None) -> Container:
        settings = Settings(
            database_url=test_database, redis_url="redis://localhost:6379/9", llm_provider="fake"
        )
        provider = llm_provider or FakeLLMProvider(responses=["{}"])
        container = Container.build(settings, llm_provider=provider)
        built.append(container)
        return container

    yield make
    for container in built:
        await container.aclose()


@pytest.fixture
async def db_container(container_factory: ContainerFactory) -> Container:
    return container_factory(None)


@pytest.fixture
async def db_client(db_container: Container) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(db_container))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
