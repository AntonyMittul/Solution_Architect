from typing import Any

import structlog

from aisa.artifacts.application.ports import ArtifactRepository
from aisa.artifacts.domain.models import Artifact, ArtifactType
from aisa.blueprint.application.agents import BlueprintAgents
from aisa.blueprint.application.graph import build_blueprint_graph
from aisa.blueprint.domain.dependencies import (
    ARTIFACT_AGENT,
    ARTIFACT_DEPENDENCIES,
    STATE_KEY_TO_TYPE,
)
from aisa.intake.application.ports import RequirementRepository
from aisa.intake.domain.models import RequirementStatus
from aisa.llm.application.service import LLMContext
from aisa.orchestration.application.ports import RunEventSink, RunRepository
from aisa.projects.application.ports import ProjectRepository
from aisa.shared.clock import Clock
from aisa.shared.errors import InvalidStateError

logger = structlog.get_logger(__name__)

BLUEPRINT_KIND = "blueprint"


class BlueprintExecutor:
    """Runs the blueprint LangGraph and persists each artifact as a version with
    provenance and dependency edges. Idempotent on redelivery via the run state
    machine; a failed run is terminal (no retry-storm)."""

    def __init__(
        self,
        runs: RunRepository,
        events: RunEventSink,
        artifacts: ArtifactRepository,
        requirements: RequirementRepository,
        projects: ProjectRepository,
        agents: BlueprintAgents,
        clock: Clock,
        model: str,
        max_repairs: int = 1,
    ) -> None:
        self._runs = runs
        self._events = events
        self._artifacts = artifacts
        self._requirements = requirements
        self._projects = projects
        self._agents = agents
        self._clock = clock
        self._model = model
        self._max_repairs = max_repairs

    async def execute(self, run_id: str) -> None:
        run = await self._runs.get(run_id)
        if run.is_terminal:
            logger.info("blueprint.already_terminal", run_id=run_id, status=run.status)
            return

        run.start(self._clock.now())
        await self._runs.save(run)
        await self._events.emit(run_id, "run.status", {"status": run.status.value})

        workspace_id = run.workspace_id
        project_id = run.project_id
        if workspace_id is None or project_id is None:
            await self._fail(run_id, run, "blueprint run missing workspace/project")
            return

        try:
            requirements = await self._requirements.latest(workspace_id, project_id)
            if requirements is None or requirements.status is not RequirementStatus.CONFIRMED:
                raise InvalidStateError(
                    "Requirements must be confirmed before blueprint generation"
                )
            project = await self._projects.get(workspace_id, project_id)

            async def emit(event_type: str, payload: dict[str, object]) -> None:
                await self._events.emit(run_id, event_type, payload)

            graph = build_blueprint_graph(
                self._agents, emit, LLMContext(workspace_id, run_id), self._max_repairs
            )
            final: dict[str, Any] = await graph.ainvoke(
                {
                    "requirements": requirements.content,
                    "settings": project.settings,
                    "feedback": [],
                    "repair_count": 0,
                }
            )

            await self._persist(workspace_id, project_id, run_id, requirements.version, final)
            run.complete(self._clock.now())
            await self._runs.save(run)
            await self._events.emit(run_id, "run.completed", {"status": run.status.value})
            logger.info("blueprint.completed", run_id=run_id)
        except Exception as exc:  # mark failed; do not retry-storm
            await self._fail(run_id, run, str(exc))
            logger.exception("blueprint.failed", run_id=run_id)

    async def _persist(
        self,
        workspace_id: str,
        project_id: str,
        run_id: str,
        requirements_version: int,
        final: dict[str, Any],
    ) -> None:
        # Ensure all artifact identities first so dependency edges can reference them.
        by_type: dict[ArtifactType, Artifact] = {}
        for artifact_type in STATE_KEY_TO_TYPE.values():
            by_type[artifact_type] = await self._artifacts.ensure(
                workspace_id, project_id, artifact_type
            )

        for state_key, artifact_type in STATE_KEY_TO_TYPE.items():
            artifact = by_type[artifact_type]
            provenance = {
                "run_id": run_id,
                "agent": ARTIFACT_AGENT[artifact_type],
                "model": self._model,
                "source": "agent",
                "requirements_version": requirements_version,
            }
            await self._artifacts.append_version(
                workspace_id, artifact.id, content=final.get(state_key, {}), provenance=provenance
            )
            deps = [by_type[dep].id for dep in ARTIFACT_DEPENDENCIES[artifact_type]]
            await self._artifacts.set_dependencies(workspace_id, artifact.id, deps)
            await self._events.emit(run_id, "artifact.created", {"type": artifact_type.value})

    async def _fail(self, run_id: str, run: Any, error: str) -> None:
        run.fail(self._clock.now(), error)
        await self._runs.save(run)
        await self._events.emit(run_id, "run.failed", {"error": error})
