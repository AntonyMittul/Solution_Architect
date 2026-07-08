import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import aisa.artifacts.infrastructure.tables
import aisa.identity.infrastructure.tables
import aisa.intake.infrastructure.tables
import aisa.integrations.infrastructure.tables
import aisa.llm.infrastructure.usage
import aisa.orchestration.infrastructure.tables
import aisa.projects.infrastructure.tables
from aisa.shared.config import normalize_async_dsn
from aisa.shared.db import Base

# Table modules must be imported so Base.metadata sees every table.
_ = (
    aisa.identity.infrastructure.tables,
    aisa.orchestration.infrastructure.tables,
    aisa.projects.infrastructure.tables,
    aisa.intake.infrastructure.tables,
    aisa.integrations.infrastructure.tables,
    aisa.llm.infrastructure.usage,
    aisa.artifacts.infrastructure.tables,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Env var wins over alembic.ini (12-factor). Migrations run as the admin
# role (table owner); the app runtime uses the restricted aisa_app role.
database_url = os.environ.get("AISA_DATABASE_ADMIN_URL") or os.environ.get("AISA_DATABASE_URL")
if database_url:
    # Managed Postgres hands out postgres:// URLs; our engine needs asyncpg.
    config.set_main_option("sqlalchemy.url", normalize_async_dsn(database_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
