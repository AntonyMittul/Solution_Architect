from datetime import datetime

from sqlalchemy import func, select

from aisa.llm.infrastructure.usage import LLMUsageRow
from aisa.shared.db import SessionFactory


class SqlUsageStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def tokens_since(self, workspace_id: str, since: datetime) -> tuple[int, int]:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(
                        func.coalesce(func.sum(LLMUsageRow.input_tokens), 0),
                        func.coalesce(func.sum(LLMUsageRow.output_tokens), 0),
                    ).where(
                        LLMUsageRow.workspace_id == workspace_id,
                        LLMUsageRow.created_at >= since,
                    )
                )
            ).one()
            return int(row[0]), int(row[1])
