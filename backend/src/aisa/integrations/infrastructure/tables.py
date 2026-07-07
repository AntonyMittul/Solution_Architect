from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aisa.shared.db import Base


class McpServerRow(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_mcp_server_name"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    transport: Mapped[str] = mapped_column(String(24), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    trust: Mapped[str] = mapped_column(String(16), nullable=False)
    tool_allowlist: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[str] = mapped_column(String(26), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProvisioningPlanRow(Base):
    __tablename__ = "provisioning_plans"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    project_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by: Mapped[str] = mapped_column(String(26), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ToolInvocationRow(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    server_id: Mapped[str] = mapped_column(String(26), nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
