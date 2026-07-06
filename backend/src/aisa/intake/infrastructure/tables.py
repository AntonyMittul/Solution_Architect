from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aisa.shared.db import Base


class ThreadRow(Base):
    __tablename__ = "threads"
    __table_args__ = (UniqueConstraint("project_id", name="uq_threads_project"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    project_id: Mapped[str] = mapped_column(String(26), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(26))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RequirementDocRow(Base):
    __tablename__ = "requirement_docs"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_requirements_version"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    project_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
