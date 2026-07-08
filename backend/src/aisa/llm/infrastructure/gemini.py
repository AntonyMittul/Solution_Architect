import asyncio
import random
import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog
from google.genai import types
from pydantic import BaseModel

from aisa.llm.application.service import LLMError
from aisa.llm.domain.messages import LLMMessage, MessageRole, ModelTier, RawCompletion, TokenUsage

logger = structlog.get_logger(__name__)

# Gemini reports rate limiting as 429/RESOURCE_EXHAUSTED and often suggests how
# long to wait (e.g. "'retryDelay': '26s'"). Honour that; otherwise back off far
# longer than for ordinary transient errors, since RPM limits reset on a clock.
_RETRY_DELAY = re.compile(r"retryDelay'?:?\s*'?(\d+(?:\.\d+)?)s")


def _is_rate_limited(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


def _suggested_delay(exc: Exception) -> float | None:
    match = _RETRY_DELAY.search(str(exc))
    return float(match.group(1)) if match else None


class GeminiClient(Protocol):
    """Minimal surface of google-genai's async client, so the provider can be
    unit-tested with a stub (no network)."""

    @property
    def aio(self) -> Any: ...


class GeminiProvider:
    """LLMProvider backed by Google Gemini via the google-genai SDK.

    Uses native structured output (response_mime_type=application/json +
    response_schema) so the model returns schema-shaped JSON. Transient errors
    are retried with exponential backoff."""

    def __init__(
        self,
        client: GeminiClient,
        models: dict[ModelTier, str],
        *,
        max_output_tokens: int = 8192,
        temperature: float = 0.2,
        max_attempts: int = 3,
        backoff_base: float = 0.5,
        rate_limit_backoff: float = 20.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._models = models
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._rate_limit_backoff = rate_limit_backoff
        self._sleep = sleep

    def _delay_for(self, exc: Exception, attempt: int) -> float:
        if _is_rate_limited(exc):
            base = _suggested_delay(exc) or self._rate_limit_backoff * (2**attempt)
        else:
            base = self._backoff_base * (2**attempt)
        return base + random.uniform(0, base * 0.25)  # jitter (doc 03 NFR-3)

    async def generate(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        response_model: type[BaseModel],
        tier: ModelTier,
    ) -> RawCompletion:
        model = self._models[tier]
        contents = [
            {
                "role": "user" if m.role is MessageRole.USER else "model",
                "parts": [{"text": m.content}],
            }
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=response_model,
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
        )

        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                response = await self._client.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
                return RawCompletion(
                    text=response.text or "",
                    usage=_usage_from(response, model),
                )
            except Exception as exc:  # provider errors are opaque; retry then surface
                last_error = exc
                rate_limited = _is_rate_limited(exc)
                logger.warning(
                    "llm.gemini_retry",
                    attempt=attempt,
                    model=model,
                    rate_limited=rate_limited,
                    error=str(exc),
                )
                if attempt < self._max_attempts - 1:
                    await self._sleep(self._delay_for(exc, attempt))

        if last_error is not None and _is_rate_limited(last_error):
            raise LLMError(
                "Gemini rate limit / quota exhausted. Wait for the quota window to reset, "
                "or run with AISA_LLM_PROVIDER=fake."
            ) from last_error
        raise LLMError(f"Gemini request failed after {self._max_attempts} attempts") from last_error


def _usage_from(response: Any, model: str) -> TokenUsage:
    meta = getattr(response, "usage_metadata", None)
    return TokenUsage(
        model=model,
        input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
        output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
    )
