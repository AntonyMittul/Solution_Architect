from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aisa.shared.db import Base


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(26), index=True)
    project_id: Mapped[str | None] = mapped_column(String(26), index=True)
    triggered_by: Mapped[str | None] = mapped_column(String(26))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentEventRow(Base):
    __tablename__ = "agent_events"

    run_id: Mapped[str] = mapped_column(String(26), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
