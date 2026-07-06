from dataclasses import dataclass

from aisa.intake.application.executor import INTAKE_KIND
from aisa.intake.application.ports import (
    MessageRepository,
    RequirementRepository,
    ThreadRepository,
)
from aisa.intake.domain.models import Message, RequirementDoc, ThreadRole
from aisa.orchestration.application.ports import RunRepository
from aisa.orchestration.application.use_cases import CreateRun, EnqueueRunContinuation
from aisa.shared.audit import AuditEntry, AuditLogger
from aisa.shared.authz import Actor, Permission
from aisa.shared.clock import Clock
from aisa.shared.errors import ForbiddenError, NotFoundError


@dataclass(frozen=True)
class PostMessageResult:
    thread_id: str
    run_id: str
    resumed: bool


class PostMessage:
    """Append a user message and (re)start the intake conversation for a project.

    If an intake run is paused awaiting the user's answer, this resumes it;
    otherwise it starts a fresh intake run."""

    def __init__(
        self,
        threads: ThreadRepository,
        messages: MessageRepository,
        runs: RunRepository,
        create_run: CreateRun,
        continue_run: EnqueueRunContinuation,
        clock: Clock,
    ) -> None:
        self._threads = threads
        self._messages = messages
        self._runs = runs
        self._create_run = create_run
        self._continue_run = continue_run
        self._clock = clock

    async def execute(self, actor: Actor, project_id: str, text: str) -> PostMessageResult:
        actor.require(Permission.RUN_TRIGGER)
        if not actor.email_verified:
            raise ForbiddenError("Verify your email address before starting a design")
        if not text.strip():
            raise NotFoundError("Message text must not be empty")

        thread = await self._threads.ensure_for_project(actor.workspace_id, project_id)
        await self._messages.append(
            actor.workspace_id,
            thread.id,
            role=ThreadRole.USER,
            content={"text": text.strip()},
            run_id=None,
            now=self._clock.now(),
        )

        active = await self._runs.latest_for_project(project_id, INTAKE_KIND)
        if active is not None and active.awaiting_input:
            await self._continue_run.execute(active.id)
            return PostMessageResult(thread_id=thread.id, run_id=active.id, resumed=True)

        run = await self._create_run.execute(
            INTAKE_KIND,
            workspace_id=actor.workspace_id,
            project_id=project_id,
            triggered_by=actor.user_id,
        )
        return PostMessageResult(thread_id=thread.id, run_id=run.id, resumed=False)


class ListMessages:
    def __init__(self, threads: ThreadRepository, messages: MessageRepository) -> None:
        self._threads = threads
        self._messages = messages

    async def execute(self, actor: Actor, project_id: str) -> list[Message]:
        actor.require(Permission.PROJECT_READ)
        thread = await self._threads.get_for_project(actor.workspace_id, project_id)
        if thread is None:
            return []
        return await self._messages.list_for_thread(actor.workspace_id, thread.id)


class GetRequirements:
    def __init__(self, requirements: RequirementRepository) -> None:
        self._requirements = requirements

    async def execute(self, actor: Actor, project_id: str) -> RequirementDoc:
        actor.require(Permission.PROJECT_READ)
        doc = await self._requirements.latest(actor.workspace_id, project_id)
        if doc is None:
            raise NotFoundError("No requirements have been generated yet")
        return doc


class ConfirmRequirements:
    def __init__(self, requirements: RequirementRepository, audit: AuditLogger) -> None:
        self._requirements = requirements
        self._audit = audit

    async def execute(self, actor: Actor, project_id: str) -> RequirementDoc:
        actor.require(Permission.PROJECT_WRITE)
        doc = await self._requirements.confirm_latest(actor.workspace_id, project_id)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="requirements.confirmed",
                workspace_id=actor.workspace_id,
                target=f"project:{project_id}",
                metadata={"version": doc.version},
            )
        )
        return doc
