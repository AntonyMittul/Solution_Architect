from typing import Protocol

from pydantic import BaseModel

from aisa.llm.domain.messages import LLMMessage, ModelTier, RawCompletion, TokenUsage


class LLMProvider(Protocol):
    """A concrete model provider (Gemini, or the deterministic fake).

    Returns raw model text plus token usage; JSON validation and retry live in
    the provider-agnostic StructuredLLM service above this port."""

    async def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_model: type[BaseModel],
        tier: ModelTier,
    ) -> RawCompletion: ...


class UsageRecorder(Protocol):
    async def record(
        self, usage: TokenUsage, *, workspace_id: str | None, run_id: str | None
    ) -> None: ...
