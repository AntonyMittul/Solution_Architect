from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

SessionFactory = Callable[[], AsyncSession]


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
