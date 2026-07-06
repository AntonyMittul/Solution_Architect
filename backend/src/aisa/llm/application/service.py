from dataclasses import dataclass
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from aisa.llm.application.ports import LLMProvider, UsageRecorder
from aisa.llm.domain.messages import LLMMessage, MessageRole, ModelTier
from aisa.shared.errors import AppError

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(AppError):
    code = "llm_error"
    title = "LLM request failed"
    status = 502


@dataclass(frozen=True)
class LLMContext:
    workspace_id: str | None = None
    run_id: str | None = None


class StructuredLLM:
    """Provider-agnostic structured completion.

    Calls the provider, validates the JSON against a Pydantic schema, and on
    validation failure feeds the error back to the model and retries. Token
    usage is recorded for every attempt (billed regardless of validity)."""

    def __init__(
        self,
        provider: LLMProvider,
        usage_recorder: UsageRecorder,
        max_validation_retries: int = 2,
    ) -> None:
        self._provider = provider
        self._usage_recorder = usage_recorder
        self._max_validation_retries = max_validation_retries

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        schema: type[T],
        ctx: LLMContext,
        tier: ModelTier = ModelTier.QUALITY,
    ) -> T:
        conversation = list(messages)
        last_error: ValidationError | None = None

        for attempt in range(self._max_validation_retries + 1):
            completion = await self._provider.generate(
                system=system, messages=conversation, response_model=schema, tier=tier
            )
            await self._usage_recorder.record(
                completion.usage, workspace_id=ctx.workspace_id, run_id=ctx.run_id
            )
            try:
                return schema.model_validate_json(completion.text)
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "llm.validation_retry",
                    attempt=attempt,
                    run_id=ctx.run_id,
                    error_count=exc.error_count(),
                )
                conversation = [
                    *conversation,
                    LLMMessage(MessageRole.ASSISTANT, completion.text),
                    LLMMessage(
                        MessageRole.USER,
                        f"Your previous reply did not match the required schema "
                        f"({exc.error_count()} errors). Return ONLY valid JSON matching "
                        f"the schema. Details: {exc}",
                    ),
                ]

        raise LLMError(f"Model output failed schema validation after retries: {last_error}")
