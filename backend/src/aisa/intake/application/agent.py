import json
from importlib import resources

from aisa.intake.domain.models import Message, ThreadRole
from aisa.intake.domain.schemas import AnalystTurn
from aisa.llm.application.service import LLMContext, StructuredLLM
from aisa.llm.domain.messages import LLMMessage, MessageRole, ModelTier

PROMPT_VERSION = "requirements_analyst_v1"


def _load_prompt() -> str:
    return (
        resources.files("aisa.intake.prompts").joinpath(f"{PROMPT_VERSION}.md").read_text("utf-8")
    )


class RequirementsAnalyst:
    """Turns the conversation so far into a structured requirements document plus
    clarifying questions. A thin typed agent over the LLMService port (doc 07;
    ADR-002 records the choice of this over PydanticAI)."""

    def __init__(self, llm: StructuredLLM, tier: ModelTier = ModelTier.QUALITY) -> None:
        self._llm = llm
        self._tier = tier
        self._prompt_template = _load_prompt()

    async def run(
        self,
        *,
        history: list[Message],
        project_settings: dict[str, object],
        round_index: int,
        max_rounds: int,
        ctx: LLMContext,
    ) -> AnalystTurn:
        system = self._prompt_template.format(
            project_context=json.dumps(project_settings or {}, indent=2),
            round_number=round_index + 1,
            max_rounds=max_rounds,
        )
        messages = [
            LLMMessage(
                role=MessageRole.USER if m.role is ThreadRole.USER else MessageRole.ASSISTANT,
                content=m.text,
            )
            for m in history
            if m.text
        ]
        return await self._llm.complete(
            system=system, messages=messages, schema=AnalystTurn, ctx=ctx, tier=self._tier
        )
