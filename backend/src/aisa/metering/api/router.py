from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from aisa.metering.domain.plan import UsageSummary
from aisa.platform.api.deps import ContainerDep, CurrentActor

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["metering"])


class UsageResponse(BaseModel):
    plan: str
    period_start: datetime
    runs_this_month: int
    monthly_run_quota: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    per_run_token_budget: int

    @classmethod
    def from_domain(cls, summary: UsageSummary) -> "UsageResponse":
        return cls(
            plan=summary.plan,
            period_start=summary.period_start,
            runs_this_month=summary.runs_this_month,
            monthly_run_quota=summary.monthly_run_quota,
            input_tokens=summary.input_tokens,
            output_tokens=summary.output_tokens,
            total_tokens=summary.input_tokens + summary.output_tokens,
            estimated_cost_usd=summary.estimated_cost_usd,
            per_run_token_budget=summary.per_run_token_budget,
        )


@router.get("/usage")
async def get_usage(actor: CurrentActor, container: ContainerDep) -> UsageResponse:
    summary = await container.usage_service.summary(actor.workspace_id)
    return UsageResponse.from_domain(summary)
