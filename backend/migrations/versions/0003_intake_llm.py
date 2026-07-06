"""Intake: runs scoping, threads, messages, requirement_docs, llm_usage + RLS.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = ("threads", "messages", "requirement_docs")


def upgrade() -> None:
    # runs gain workspace/project scoping (expand: nullable, no backfill needed).
    op.add_column("runs", sa.Column("workspace_id", sa.String(26)))
    op.add_column("runs", sa.Column("project_id", sa.String(26)))
    op.add_column("runs", sa.Column("triggered_by", sa.String(26)))
    op.add_column("runs", sa.Column("input", JSONB(), nullable=False, server_default="{}"))
    op.create_index("idx_runs_workspace", "runs", ["workspace_id"])
    op.create_index("idx_runs_project", "runs", ["project_id"])

    op.create_table(
        "threads",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("project_id", sa.String(26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_threads_project"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("thread_id", sa.String(26), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("run_id", sa.String(26)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_messages_thread", "messages", ["thread_id"])

    op.create_table(
        "requirement_docs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("project_id", sa.String(26), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "version", name="uq_requirements_version"),
    )
    op.create_index("idx_requirements_project", "requirement_docs", ["project_id"])

    op.create_table(
        "llm_usage",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26)),
        sa.Column("run_id", sa.String(26)),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_llm_usage_workspace", "llm_usage", ["workspace_id"])

    # RLS tenant isolation on the new tenant-owned tables (doc 09 §3).
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id', true))"
        )


def downgrade() -> None:
    for table in _TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.drop_index("idx_llm_usage_workspace", table_name="llm_usage")
    op.drop_table("llm_usage")
    op.drop_index("idx_requirements_project", table_name="requirement_docs")
    op.drop_table("requirement_docs")
    op.drop_index("idx_messages_thread", table_name="messages")
    op.drop_table("messages")
    op.drop_table("threads")
    op.drop_index("idx_runs_project", table_name="runs")
    op.drop_index("idx_runs_workspace", table_name="runs")
    op.drop_column("runs", "input")
    op.drop_column("runs", "triggered_by")
    op.drop_column("runs", "project_id")
    op.drop_column("runs", "workspace_id")
