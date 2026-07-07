from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


@dataclass(frozen=True)
class PlanLimits:
    monthly_run_quota: int
    per_run_token_budget: int


class PlanCatalog:
    """Resolves a workspace's plan string to its limits, config-driven."""

    def __init__(self, limits: dict[str, PlanLimits], default: PlanLimits) -> None:
        self._limits = limits
        self._default = default

    def for_plan(self, plan: str) -> PlanLimits:
        return self._limits.get(plan, self._default)


@dataclass(frozen=True)
class UsageSummary:
    plan: str
    period_start: datetime
    runs_this_month: int
    monthly_run_quota: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    per_run_token_budget: int
