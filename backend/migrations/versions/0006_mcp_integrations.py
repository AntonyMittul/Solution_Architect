"""MCP integrations: servers, provisioning plans, tool invocations + RLS.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = ("mcp_servers", "provisioning_plans", "tool_invocations")


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("transport", sa.String(24), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("trust", sa.String(16), nullable=False),
        sa.Column("tool_allowlist", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_mcp_server_name"),
    )

    op.create_table(
        "provisioning_plans",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("project_id", sa.String(26), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_plans_project", "provisioning_plans", ["project_id"])

    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("plan_id", sa.String(26), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.String(26), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("arguments", JSONB(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result", JSONB()),
    )
    op.create_index("idx_invocations_plan", "tool_invocations", ["plan_id"])

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
    op.drop_index("idx_invocations_plan", table_name="tool_invocations")
    op.drop_table("tool_invocations")
    op.drop_index("idx_plans_project", table_name="provisioning_plans")
    op.drop_table("provisioning_plans")
    op.drop_table("mcp_servers")
