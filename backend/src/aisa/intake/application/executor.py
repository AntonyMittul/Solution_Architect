import structlog

from aisa.intake.application.agent import PROMPT_VERSION, RequirementsAnalyst
from aisa.intake.application.ports import (
    MessageRepository,
    RequirementRepository,
    ThreadRepository,
)
from aisa.intake.domain.models import ThreadRole
from aisa.llm.application.service import LLMContext
from aisa.orchestration.application.ports import RunEventSink, RunRepository
from aisa.projects.application.ports import ProjectRepository
from aisa.shared.clock import Clock

logger = structlog.get_logger(__name__)

INTAKE_KIND = "intake"


class IntakeExecutor:
    """Runs one turn of the requirements intake conversation.

    Implements the orchestration RunExecutor contract: idempotent on redelivery,
    resumable from needs_input. Produces a draft requirements version and an
    assistant message each turn; pauses at needs_input while clarifying
    questions remain and the round cap is not reached."""

    def __init__(
        self,
        runs: RunRepository,
        events: RunEventSink,
        threads: ThreadRepository,
        messages: MessageRepository,
        requirements: RequirementRepository,
        projects: ProjectRepository,
        analyst: RequirementsAnalyst,
        clock: Clock,
        max_rounds: int,
    ) -> None:
        self._runs = runs
        self._events = events
        self._threads = threads
        self._messages = messages
        self._requirements = requirements
        self._projects = projects
        self._analyst = analyst
        self._clock = clock
        self._max_rounds = max_rounds

    async def execute(self, run_id: str) -> None:
        run = await self._runs.get(run_id)
        if run.is_terminal:
            logger.info("intake.already_terminal", run_id=run_id, status=run.status)
            return

        now = self._clock.now()
        if run.awaiting_input:
            run.resume(now)
        else:
            run.start(now)
        await self._runs.save(run)
        await self._events.emit(run_id, "run.status", {"status": run.status.value})

        workspace_id = run.workspace_id
        project_id = run.project_id
        if workspace_id is None or project_id is None:
            await self._finish_failed(run_id, run, "intake run missing workspace/project")
            return

        try:
            thread = await self._threads.ensure_for_project(workspace_id, project_id)
            history = await self._messages.list_for_thread(workspace_id, thread.id)
            round_index = sum(1 for m in history if m.role is ThreadRole.ASSISTANT)
            project = await self._projects.get(workspace_id, project_id)

            await self._events.emit(
                run_id, "agent.started", {"agent": "requirements_analyst", "round": round_index + 1}
            )
            turn = await self._analyst.run(
                history=history,
                project_settings=project.settings,
                round_index=round_index,
                max_rounds=self._max_rounds,
                ctx=LLMContext(workspace_id=workspace_id, run_id=run_id),
            )

            requirement = await self._requirements.append_version(
                workspace_id,
                project_id,
                content=turn.requirements.model_dump(),
                created_by=f"agent:{PROMPT_VERSION}",
                now=now,
            )
            await self._events.emit(
                run_id,
                "artifact.created",
                {"type": "requirements", "version": requirement.version},
            )

            await self._messages.append(
                workspace_id,
                thread.id,
                role=ThreadRole.ASSISTANT,
                content={
                    "text": turn.assistant_message,
                    "questions": [q.model_dump() for q in turn.clarifying_questions],
                },
                run_id=run_id,
                now=now,
            )
            await self._events.emit(run_id, "message.created", {"role": "assistant"})

            has_questions = bool(turn.clarifying_questions) and not turn.ready_to_confirm
            reached_cap = round_index + 1 >= self._max_rounds
            if has_questions and not reached_cap:
                run.await_input(now)
                await self._runs.save(run)
                await self._events.emit(
                    run_id,
                    "intake.awaiting_answer",
                    {"question_count": len(turn.clarifying_questions)},
                )
            else:
                run.complete(now)
                await self._runs.save(run)
                await self._events.emit(run_id, "run.completed", {"status": run.status.value})
        except Exception as exc:  # mark the run failed; do not retry-storm
            await self._finish_failed(run_id, run, str(exc))
            logger.exception("intake.failed", run_id=run_id)

    async def _finish_failed(self, run_id: str, run, error: str) -> None:  # type: ignore[no-untyped-def]
        run.fail(self._clock.now(), error)
        await self._runs.save(run)
        await self._events.emit(run_id, "run.failed", {"error": error})
