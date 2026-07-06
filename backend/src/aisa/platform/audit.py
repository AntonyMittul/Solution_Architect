from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aisa.shared.audit import AuditEntry
from aisa.shared.clock import Clock
from aisa.shared.db import Base, SessionFactory
from aisa.shared.ids import new_id


class AuditLogRow(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("idx_audit_ws_time", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(String(26))
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SqlAuditLogger:
    """Append-only audit writer (doc 09 §7)."""

    def __init__(self, session_factory: SessionFactory, clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def record(self, entry: AuditEntry) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                AuditLogRow(
                    id=new_id(),
                    workspace_id=entry.workspace_id,
                    actor=entry.actor,
                    action=entry.action,
                    target=entry.target,
                    metadata_=dict(entry.metadata),
                    created_at=self._clock.now(),
                )
            )
