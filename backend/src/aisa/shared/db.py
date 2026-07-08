from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = structlog.get_logger(__name__)

SessionFactory = Callable[[], AsyncSession]


async def check_rls_enforcement(engine: AsyncEngine) -> bool:
    """Tenant isolation relies on Postgres RLS. A superuser (or a role with
    BYPASSRLS) silently ignores every policy, degrading isolation to the
    application layer alone — so say so, loudly. Returns True when enforced."""
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT rolsuper OR rolbypassrls AS bypasses, rolname "
                        "FROM pg_roles WHERE rolname = current_user"
                    )
                )
            ).first()
    except Exception:  # pragma: no cover - diagnostics must never break startup
        logger.warning("db.rls_check_failed")
        return True

    if row is None:
        return True
    if row.bypasses:
        logger.error(
            "db.rls_bypassed",
            role=row.rolname,
            detail=(
                "The runtime database role bypasses row-level security. "
                "Connect as a non-superuser role without BYPASSRLS so tenant "
                "isolation is enforced by Postgres."
            ),
        )
        return False
    logger.info("db.rls_enforced", role=row.rolname)
    return True


class Base(DeclarativeBase):
    """Single declarative base; each module defines its own tables against it."""


@asynccontextmanager
async def tenant_session(
    session_factory: SessionFactory, workspace_id: str
) -> AsyncIterator[AsyncSession]:
    """Open a transaction with `app.workspace_id` set for Postgres RLS.

    Every query on RLS-protected tables inside this block is filtered to the
    workspace at the database layer — the backstop beneath application checks.
    """
    async with session_factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": workspace_id}
        )
        yield session
