from aisa.blueprint.application.executor import BLUEPRINT_KIND
from aisa.intake.application.ports import RequirementRepository
from aisa.intake.domain.models import RequirementStatus
from aisa.metering.application.service import RunGuard
from aisa.orchestration.application.use_cases import CreateRun
from aisa.orchestration.domain.run import Run
from aisa.shared.authz import Actor, Permission
from aisa.shared.errors import ForbiddenError, InvalidStateError


class CreateBlueprintRun:
    """Start a blueprint run. Gated on confirmed requirements (doc 07) and the
    workspace's monthly run quota (doc 03 NFR-4)."""

    def __init__(
        self, requirements: RequirementRepository, create_run: CreateRun, run_guard: RunGuard
    ) -> None:
        self._requirements = requirements
        self._create_run = create_run
        self._run_guard = run_guard

    async def execute(self, actor: Actor, project_id: str) -> Run:
        actor.require(Permission.RUN_TRIGGER)
        if not actor.email_verified:
            raise ForbiddenError("Verify your email address before generating a blueprint")

        requirements = await self._requirements.latest(actor.workspace_id, project_id)
        if requirements is None or requirements.status is not RequirementStatus.CONFIRMED:
            raise InvalidStateError("Confirm the requirements before generating a blueprint")

        limits = await self._run_guard.check(actor.workspace_id)
        return await self._create_run.execute(
            BLUEPRINT_KIND,
            workspace_id=actor.workspace_id,
            project_id=project_id,
            triggered_by=actor.user_id,
            input={"requirements_version": requirements.version},
            token_budget=limits.per_run_token_budget,
        )
