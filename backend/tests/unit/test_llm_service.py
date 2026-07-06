import pytest
from pydantic import BaseModel

from aisa.llm.application.service import LLMContext, LLMError, StructuredLLM
from aisa.llm.domain.messages import MessageRole
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.llm.infrastructure.usage import NullUsageRecorder


class Answer(BaseModel):
    value: int
    label: str


CTX = LLMContext(workspace_id="w1", run_id="r1")


async def test_valid_json_parses_first_try() -> None:
    provider = FakeLLMProvider(responses=['{"value": 42, "label": "ok"}'])
    llm = StructuredLLM(provider, NullUsageRecorder())
    result = await llm.complete(system="s", messages=[], schema=Answer, ctx=CTX)
    assert result == Answer(value=42, label="ok")
    assert len(provider.calls) == 1


async def test_invalid_then_valid_retries_with_feedback() -> None:
    provider = FakeLLMProvider(
        responses=['{"value": "not-an-int"}', '{"value": 7, "label": "fixed"}']
    )
    llm = StructuredLLM(provider, NullUsageRecorder())
    result = await llm.complete(system="s", messages=[], schema=Answer, ctx=CTX)
    assert result.value == 7
    # The retry fed the validation error back as an extra user turn.
    assert len(provider.calls) == 2
    _, second_call_messages = provider.calls[1]
    assert second_call_messages[-1].role is MessageRole.USER
    assert "schema" in second_call_messages[-1].content.lower()


async def test_exhausted_retries_raises_llm_error() -> None:
    provider = FakeLLMProvider(responses=['{"bad": 1}', '{"bad": 2}', '{"bad": 3}'])
    llm = StructuredLLM(provider, NullUsageRecorder(), max_validation_retries=2)
    with pytest.raises(LLMError):
        await llm.complete(system="s", messages=[], schema=Answer, ctx=CTX)
    assert len(provider.calls) == 3  # initial + 2 retries


async def test_auto_fake_generates_schema_valid_minimal_output() -> None:
    # No responses/handler: the fake fills required fields so the whole app
    # runs key-less. AnalystTurn is a good stress case (nested model + lists).
    from aisa.intake.domain.schemas import AnalystTurn

    provider = FakeLLMProvider()
    llm = StructuredLLM(provider, NullUsageRecorder())
    turn = await llm.complete(system="s", messages=[], schema=AnalystTurn, ctx=CTX)
    assert isinstance(turn, AnalystTurn)
    assert turn.clarifying_questions == []


async def test_usage_recorded_for_every_attempt() -> None:
    recorded: list[tuple[str | None, str | None]] = []

    class RecordingRecorder:
        async def record(self, usage, *, workspace_id, run_id) -> None:  # type: ignore[no-untyped-def]
            recorded.append((workspace_id, run_id))

    provider = FakeLLMProvider(responses=['{"nope": 1}', '{"value": 1, "label": "x"}'])
    llm = StructuredLLM(provider, RecordingRecorder())
    await llm.complete(system="s", messages=[], schema=Answer, ctx=CTX)
    assert recorded == [("w1", "r1"), ("w1", "r1")]  # billed even for the invalid attempt
