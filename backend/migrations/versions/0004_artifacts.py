"""Artifacts: artifacts, artifact_versions, artifact_dependencies + RLS.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = ("artifacts", "artifact_versions", "artifact_dependencies")


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("project_id", sa.String(26), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("project_id", "type", name="uq_artifact_project_type"),
    )
    op.create_index("idx_artifacts_project", "artifacts", ["project_id"])

    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("artifact_id", sa.String(26), sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("provenance", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("artifact_id", "version", name="uq_artifact_version"),
    )
    op.create_index("idx_artifact_versions_artifact", "artifact_versions", ["artifact_id"])

    op.create_table(
        "artifact_dependencies",
        sa.Column("workspace_id", sa.String(26), nullable=False),
        sa.Column("artifact_id", sa.String(26), sa.ForeignKey("artifacts.id"), primary_key=True),
        sa.Column("depends_on_id", sa.String(26), sa.ForeignKey("artifacts.id"), primary_key=True),
    )

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
    op.drop_table("artifact_dependencies")
    op.drop_index("idx_artifact_versions_artifact", table_name="artifact_versions")
    op.drop_table("artifact_versions")
    op.drop_index("idx_artifacts_project", table_name="artifacts")
    op.drop_table("artifacts")
