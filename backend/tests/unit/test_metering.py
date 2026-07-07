from datetime import UTC, datetime

import pytest

from aisa.identity.domain.models import Workspace, WorkspaceKind
from aisa.metering.application.service import RunGuard, UsageService, _month_start
from aisa.metering.domain.plan import PlanCatalog, PlanLimits
from aisa.shared.errors import QuotaExceededError
from tests.fakes import FakeClock

CATALOG = PlanCatalog(
    {"free": PlanLimits(monthly_run_quota=3, per_run_token_budget=500_000)},
    default=PlanLimits(monthly_run_quota=3, per_run_token_budget=500_000),
)
NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


class FakeWorkspaces:
    def __init__(self, plan: str = "free") -> None:
        self._plan = plan

    async def get(self, workspace_id: str) -> Workspace:
        return Workspace(
            id=workspace_id,
            slug="w",
            name="W",
            kind=WorkspaceKind.PERSONAL,
            plan=self._plan,
            created_at=NOW,
            updated_at=NOW,
        )


class FakeRuns:
    def __init__(self, count: int) -> None:
        self._count = count
        self.since_arg: datetime | None = None

    async def count_since(self, workspace_id: str, since: datetime) -> int:
        self.since_arg = since
        return self._count


class FakeUsageStore:
    def __init__(self, tokens: tuple[int, int]) -> None:
        self._tokens = tokens

    async def tokens_since(self, workspace_id: str, since: datetime) -> tuple[int, int]:
        return self._tokens


def test_month_start_truncates() -> None:
    assert _month_start(NOW) == datetime(2026, 7, 1, tzinfo=UTC)


async def test_run_guard_allows_under_quota() -> None:
    guard = RunGuard(FakeWorkspaces(), FakeRuns(count=2), CATALOG, FakeClock(NOW))
    limits = await guard.check("w1")
    assert limits.per_run_token_budget == 500_000


async def test_run_guard_rejects_at_quota() -> None:
    guard = RunGuard(FakeWorkspaces(), FakeRuns(count=3), CATALOG, FakeClock(NOW))
    with pytest.raises(QuotaExceededError):
        await guard.check("w1")


async def test_run_guard_counts_from_month_start() -> None:
    runs = FakeRuns(count=0)
    await RunGuard(FakeWorkspaces(), runs, CATALOG, FakeClock(NOW)).check("w1")
    assert runs.since_arg == datetime(2026, 7, 1, tzinfo=UTC)


async def test_usage_summary_computes_totals_and_cost() -> None:
    service = UsageService(
        FakeWorkspaces(),
        FakeRuns(count=4),
        FakeUsageStore((1_000_000, 500_000)),
        CATALOG,
        FakeClock(NOW),
        price_per_1m_tokens=0.30,
    )
    summary = await service.summary("w1")
    assert summary.plan == "free"
    assert summary.runs_this_month == 4
    assert summary.monthly_run_quota == 3
    assert summary.input_tokens == 1_000_000
    assert summary.output_tokens == 500_000
    assert summary.estimated_cost_usd == pytest.approx(0.45)  # 1.5M tokens * $0.30/M
