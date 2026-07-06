from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from aisa.llm.domain.messages import TokenUsage
from aisa.shared.clock import Clock
from aisa.shared.db import Base, SessionFactory
from aisa.shared.ids import new_id


class LLMUsageRow(Base):
    __tablename__ = "llm_usage"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(String(26), index=True)
    run_id: Mapped[str | None] = mapped_column(String(26))
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SqlUsageRecorder:
    def __init__(self, session_factory: SessionFactory, clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def record(
        self, usage: TokenUsage, *, workspace_id: str | None, run_id: str | None
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                LLMUsageRow(
                    id=new_id(),
                    workspace_id=workspace_id,
                    run_id=run_id,
                    model=usage.model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    created_at=self._clock.now(),
                )
            )


class NullUsageRecorder:
    async def record(
        self, usage: TokenUsage, *, workspace_id: str | None, run_id: str | None
    ) -> None:
        return None
