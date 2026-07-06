import json
from importlib import resources
from typing import Any, TypeVar

from pydantic import BaseModel

from aisa.blueprint.domain.schemas import (
    ApiSpec,
    ArchitectureDesign,
    ConsistencyReport,
    CostEstimate,
    DbSchema,
    DesignDocument,
    DiagramSpec,
    TechStackRecommendation,
)
from aisa.llm.application.service import LLMContext, StructuredLLM
from aisa.llm.domain.messages import LLMMessage, MessageRole, ModelTier

T = TypeVar("T", bound=BaseModel)
Json = dict[str, Any]

# prompt version tags -> file names (recorded in artifact provenance)
PROMPTS = {
    "solution_designer": "solution_designer_v1",
    "tech_stack_recommender": "tech_stack_recommender_v1",
    "api_designer": "api_designer_v1",
    "data_modeler": "data_modeler_v1",
    "diagram_generator": "diagram_generator_v1",
    "cost_estimator": "cost_estimator_v1",
    "design_reviewer": "design_reviewer_v1",
    "docs_writer": "docs_writer_v1",
}


def _load(name: str) -> str:
    return resources.files("aisa.blueprint.prompts").joinpath(f"{name}.md").read_text("utf-8")


class BlueprintAgents:
    """Thin typed agents over the LLM port (ADR-002). Each method formats a
    payload as the user message and returns the validated artifact model."""

    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm
        self._prompts = {key: _load(name) for key, name in PROMPTS.items()}

    async def _run(
        self,
        agent: str,
        payload: dict[str, object],
        schema: type[T],
        ctx: LLMContext,
        tier: ModelTier = ModelTier.QUALITY,
    ) -> T:
        message = LLMMessage(MessageRole.USER, json.dumps(payload, default=str))
        return await self._llm.complete(
            system=self._prompts[agent], messages=[message], schema=schema, ctx=ctx, tier=tier
        )

    async def design(
        self, requirements: Json, settings: Json, feedback: list[str], ctx: LLMContext
    ) -> ArchitectureDesign:
        return await self._run(
            "solution_designer",
            {"requirements": requirements, "settings": settings, "reviewer_feedback": feedback},
            ArchitectureDesign,
            ctx,
        )

    async def tech_stack(
        self, architecture: Json, settings: Json, ctx: LLMContext
    ) -> TechStackRecommendation:
        return await self._run(
            "tech_stack_recommender",
            {"architecture": architecture, "settings": settings},
            TechStackRecommendation,
            ctx,
        )

    async def api(self, architecture: Json, ctx: LLMContext) -> ApiSpec:
        return await self._run(
            "api_designer", {"architecture": architecture}, ApiSpec, ctx, ModelTier.FAST
        )

    async def data_model(self, architecture: Json, api_spec: Json, ctx: LLMContext) -> DbSchema:
        return await self._run(
            "data_modeler",
            {"architecture": architecture, "api_spec": api_spec},
            DbSchema,
            ctx,
        )

    async def diagram(self, architecture: Json, ctx: LLMContext) -> DiagramSpec:
        return await self._run(
            "diagram_generator", {"architecture": architecture}, DiagramSpec, ctx, ModelTier.FAST
        )

    async def cost(
        self, architecture: Json, tech_stack: Json, settings: Json, ctx: LLMContext
    ) -> CostEstimate:
        return await self._run(
            "cost_estimator",
            {"architecture": architecture, "tech_stack": tech_stack, "settings": settings},
            CostEstimate,
            ctx,
            ModelTier.FAST,
        )

    async def review(self, artifacts: Json, ctx: LLMContext) -> ConsistencyReport:
        return await self._run("design_reviewer", artifacts, ConsistencyReport, ctx)

    async def docs(self, artifacts: Json, ctx: LLMContext) -> DesignDocument:
        return await self._run("docs_writer", artifacts, DesignDocument, ctx, ModelTier.FAST)
