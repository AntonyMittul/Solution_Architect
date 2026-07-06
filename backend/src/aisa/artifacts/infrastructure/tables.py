from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aisa.shared.db import Base


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("project_id", "type", name="uq_artifact_project_type"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    project_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ArtifactVersionRow(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (UniqueConstraint("artifact_id", "version", name="uq_artifact_version"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("artifacts.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactDependencyRow(Base):
    __tablename__ = "artifact_dependencies"

    workspace_id: Mapped[str] = mapped_column(String(26), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("artifacts.id"), primary_key=True
    )
    depends_on_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("artifacts.id"), primary_key=True
    )
