from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel

from aisa.llm.application.service import LLMError
from aisa.llm.domain.messages import LLMMessage, MessageRole, ModelTier
from aisa.llm.infrastructure.gemini import GeminiProvider


class Answer(BaseModel):
    value: int


@dataclass
class _StubResponse:
    text: str
    usage_metadata: Any


@dataclass
class _Usage:
    prompt_token_count: int
    candidates_token_count: int


class _StubModels:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class _StubClient:
    def __init__(self, responses: list[Any]) -> None:
        self._models = _StubModels(responses)

    @property
    def aio(self) -> Any:
        return type("Aio", (), {"models": self._models})()

    @property
    def models(self) -> _StubModels:
        return self._models


MODELS = {ModelTier.QUALITY: "gemini-3.1-flash-lite", ModelTier.FAST: "gemini-3.1-flash-lite"}


async def test_maps_messages_config_and_usage() -> None:
    client = _StubClient([_StubResponse('{"value": 5}', _Usage(120, 34))])
    provider = GeminiProvider(client, MODELS)

    result = await provider.generate(
        system="you are the analyst",
        messages=[
            LLMMessage(MessageRole.USER, "hi"),
            LLMMessage(MessageRole.ASSISTANT, "hello"),
        ],
        response_model=Answer,
        tier=ModelTier.QUALITY,
    )

    assert result.text == '{"value": 5}'
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 34
    assert result.usage.model == "gemini-3.1-flash-lite"

    call = client.models.calls[0]
    assert call["model"] == "gemini-3.1-flash-lite"
    # user -> "user", assistant -> "model"
    assert [c["role"] for c in call["contents"]] == ["user", "model"]
    assert call["config"].system_instruction == "you are the analyst"
    assert call["config"].response_mime_type == "application/json"


async def test_retries_transient_errors_then_succeeds() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = _StubClient([RuntimeError("503"), _StubResponse('{"value": 1}', _Usage(1, 1))])
    provider = GeminiProvider(client, MODELS, max_attempts=3, sleep=fake_sleep)

    result = await provider.generate(
        system="s", messages=[], response_model=Answer, tier=ModelTier.FAST
    )
    assert result.text == '{"value": 1}'
    assert len(sleeps) == 1  # backed off once before the successful retry


async def test_rate_limit_honours_suggested_retry_delay() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    rate_limited = RuntimeError(
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429}, 'retryDelay': '26s'}"
    )
    client = _StubClient([rate_limited, _StubResponse('{"value": 1}', _Usage(1, 1))])
    provider = GeminiProvider(client, MODELS, max_attempts=3, sleep=fake_sleep)

    await provider.generate(system="s", messages=[], response_model=Answer, tier=ModelTier.FAST)
    # Waits ~26s (the API's own suggestion) plus jitter — not the 0.5s default.
    assert 26.0 <= sleeps[0] <= 33.0


async def test_rate_limit_without_hint_backs_off_far_longer_than_transient() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = _StubClient(
        [RuntimeError("429 RESOURCE_EXHAUSTED"), _StubResponse('{"value": 1}', _Usage(1, 1))]
    )
    provider = GeminiProvider(
        client, MODELS, max_attempts=3, rate_limit_backoff=20.0, sleep=fake_sleep
    )
    await provider.generate(system="s", messages=[], response_model=Answer, tier=ModelTier.FAST)
    assert sleeps[0] >= 20.0  # vs 0.5s for an ordinary transient error


async def test_rate_limit_exhaustion_raises_actionable_error() -> None:
    async def fake_sleep(seconds: float) -> None:
        return None

    client = _StubClient([RuntimeError("429 RESOURCE_EXHAUSTED")] * 2)
    provider = GeminiProvider(client, MODELS, max_attempts=2, sleep=fake_sleep)
    with pytest.raises(LLMError, match="rate limit"):
        await provider.generate(system="s", messages=[], response_model=Answer, tier=ModelTier.FAST)


async def test_raises_after_exhausting_attempts() -> None:
    async def fake_sleep(seconds: float) -> None:
        return None

    client = _StubClient([RuntimeError("x"), RuntimeError("y")])
    provider = GeminiProvider(client, MODELS, max_attempts=2, sleep=fake_sleep)

    with pytest.raises(LLMError):
        await provider.generate(system="s", messages=[], response_model=Answer, tier=ModelTier.FAST)
