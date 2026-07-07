from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aisa.orchestration.domain.run import Run, RunStatus
from aisa.orchestration.infrastructure.tables import RunRow
from aisa.shared.errors import NotFoundError

SessionFactory = Callable[[], AsyncSession]


class SqlAlchemyRunRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, run: Run) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(_to_row(run))

    async def get(self, run_id: str) -> Run:
        async with self._session_factory() as session:
            row = await session.get(RunRow, run_id)
            if row is None:
                raise NotFoundError(f"Run '{run_id}' not found")
            return _to_domain(row)

    async def save(self, run: Run) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(RunRow, run.id)
            if row is None:
                raise NotFoundError(f"Run '{run.id}' not found")
            row.status = run.status.value
            row.error = run.error
            row.started_at = run.started_at
            row.finished_at = run.finished_at

    async def latest_for_project(self, project_id: str, kind: str) -> Run | None:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RunRow)
                .where(RunRow.project_id == project_id, RunRow.kind == kind)
                .order_by(RunRow.created_at.desc())
                .limit(1)
            )
            return _to_domain(row) if row is not None else None

    async def count_since(self, workspace_id: str, since: datetime) -> int:
        async with self._session_factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(RunRow)
                .where(RunRow.workspace_id == workspace_id, RunRow.created_at >= since)
            )
            return int(count or 0)


def _to_row(run: Run) -> RunRow:
    return RunRow(
        id=run.id,
        kind=run.kind,
        status=run.status.value,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        triggered_by=run.triggered_by,
        input=dict(run.input),
        token_budget=run.token_budget,
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _to_domain(row: RunRow) -> Run:
    return Run(
        id=row.id,
        kind=row.kind,
        status=RunStatus(row.status),
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        triggered_by=row.triggered_by,
        input=dict(row.input),
        token_budget=row.token_budget,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )
