from dataclasses import dataclass
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from aisa.llm.application.ports import LLMProvider, RunTokenMeter, UsageRecorder
from aisa.llm.domain.messages import LLMMessage, MessageRole, ModelTier
from aisa.shared.errors import AppError, BudgetExceededError
from aisa.shared.telemetry import get_tracer

logger = structlog.get_logger(__name__)
_tracer = get_tracer("aisa.llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(AppError):
    code = "llm_error"
    title = "LLM request failed"
    status = 502


@dataclass(frozen=True)
class LLMContext:
    workspace_id: str | None = None
    run_id: str | None = None
    token_budget: int | None = None  # None or 0 => unlimited


class _NoBudgetMeter:
    """Default meter: never enforces a budget (used when none is wired)."""

    async def add(self, run_id: str, tokens: int) -> int:
        return 0


class StructuredLLM:
    """Provider-agnostic structured completion.

    Calls the provider, validates the JSON against a Pydantic schema, and on
    validation failure feeds the error back to the model and retries. Token
    usage is recorded for every attempt (billed regardless of validity), and a
    per-run token budget is enforced when the context carries one."""

    def __init__(
        self,
        provider: LLMProvider,
        usage_recorder: UsageRecorder,
        max_validation_retries: int = 2,
        token_meter: RunTokenMeter | None = None,
    ) -> None:
        self._provider = provider
        self._usage_recorder = usage_recorder
        self._max_validation_retries = max_validation_retries
        self._token_meter: RunTokenMeter = token_meter or _NoBudgetMeter()

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

        with _tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("aisa.schema", schema.__name__)
            if ctx.run_id:
                span.set_attribute("aisa.run_id", ctx.run_id)

            for attempt in range(self._max_validation_retries + 1):
                completion = await self._provider.generate(
                    system=system, messages=conversation, response_model=schema, tier=tier
                )
                span.set_attribute("gen_ai.response.model", completion.usage.model)
                span.set_attribute("gen_ai.usage.input_tokens", completion.usage.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", completion.usage.output_tokens)
                span.set_attribute("aisa.llm_attempts", attempt + 1)
                await self._usage_recorder.record(
                    completion.usage, workspace_id=ctx.workspace_id, run_id=ctx.run_id
                )
                await self._enforce_budget(
                    ctx, completion.usage.input_tokens + completion.usage.output_tokens
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

    async def _enforce_budget(self, ctx: LLMContext, tokens: int) -> None:
        if not ctx.token_budget or ctx.run_id is None:
            return
        total = await self._token_meter.add(ctx.run_id, tokens)
        if total > ctx.token_budget:
            logger.warning(
                "llm.budget_exceeded", run_id=ctx.run_id, total=total, budget=ctx.token_budget
            )
            raise BudgetExceededError(
                f"Run exceeded its token budget ({ctx.token_budget:,} tokens)."
            )
