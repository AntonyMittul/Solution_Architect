from datetime import datetime

import structlog

from aisa.identity.application.ports import WorkspaceRepository
from aisa.metering.application.ports import UsageStore
from aisa.metering.domain.plan import PlanCatalog, PlanLimits, UsageSummary
from aisa.orchestration.application.ports import RunRepository
from aisa.shared.clock import Clock
from aisa.shared.errors import QuotaExceededError

logger = structlog.get_logger(__name__)


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class RunGuard:
    """Enforces the monthly run quota at run-creation time (doc 03 NFR-4).

    Returns the plan's limits so callers can also apply the per-run token
    budget once that lands."""

    def __init__(
        self,
        workspaces: WorkspaceRepository,
        runs: RunRepository,
        catalog: PlanCatalog,
        clock: Clock,
    ) -> None:
        self._workspaces = workspaces
        self._runs = runs
        self._catalog = catalog
        self._clock = clock

    async def check(self, workspace_id: str) -> PlanLimits:
        workspace = await self._workspaces.get(workspace_id)
        limits = self._catalog.for_plan(workspace.plan)
        used = await self._runs.count_since(workspace_id, _month_start(self._clock.now()))
        if used >= limits.monthly_run_quota:
            logger.info("metering.quota_exceeded", workspace_id=workspace_id, used=used)
            raise QuotaExceededError(
                f"Monthly run limit reached ({limits.monthly_run_quota} on the "
                f"'{workspace.plan}' plan). Upgrade or wait for the next cycle."
            )
        return limits


class UsageService:
    def __init__(
        self,
        workspaces: WorkspaceRepository,
        runs: RunRepository,
        usage_store: UsageStore,
        catalog: PlanCatalog,
        clock: Clock,
        price_per_1m_tokens: float,
    ) -> None:
        self._workspaces = workspaces
        self._runs = runs
        self._usage_store = usage_store
        self._catalog = catalog
        self._clock = clock
        self._price_per_1m_tokens = price_per_1m_tokens

    async def summary(self, workspace_id: str) -> UsageSummary:
        workspace = await self._workspaces.get(workspace_id)
        limits = self._catalog.for_plan(workspace.plan)
        since = _month_start(self._clock.now())
        runs = await self._runs.count_since(workspace_id, since)
        input_tokens, output_tokens = await self._usage_store.tokens_since(workspace_id, since)
        cost = round((input_tokens + output_tokens) / 1_000_000 * self._price_per_1m_tokens, 4)
        return UsageSummary(
            plan=workspace.plan,
            period_start=since,
            runs_this_month=runs,
            monthly_run_quota=limits.monthly_run_quota,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            per_run_token_budget=limits.per_run_token_budget,
        )
