from datetime import UTC, datetime

from aisa.intake.application.agent import RequirementsAnalyst
from aisa.intake.domain.models import Message, ThreadRole
from aisa.intake.domain.schemas import AnalystTurn
from aisa.llm.application.service import LLMContext, StructuredLLM
from aisa.llm.domain.messages import LLMMessage, MessageRole
from aisa.llm.infrastructure.fake import FakeLLMProvider
from aisa.llm.infrastructure.usage import NullUsageRecorder

NOW = datetime(2026, 7, 6, tzinfo=UTC)


def user_message(text: str) -> Message:
    return Message(
        id="m1",
        workspace_id="w1",
        thread_id="t1",
        role=ThreadRole.USER,
        content={"text": text},
        run_id=None,
        created_at=NOW,
    )


def _turn_json(*, ready: bool, questions: list[str]) -> str:
    return AnalystTurn(
        assistant_message="Here is what I captured.",
        requirements={
            "summary": "A food delivery app",
            "goals": ["Serve 1M users"],
            "actors": ["customer", "courier"],
            "functional_requirements": ["place order"],
            "non_functional_requirements": ["99.9% uptime"],
            "constraints": [],
            "assumptions": ["AWS target"],
            "open_questions": questions,
        },
        clarifying_questions=[
            {"id": f"q{i}", "question": q, "why": "matters"} for i, q in enumerate(questions)
        ],
        ready_to_confirm=ready,
    ).model_dump_json()


async def test_analyst_maps_history_and_returns_parsed_turn() -> None:
    provider = FakeLLMProvider(responses=[_turn_json(ready=False, questions=["What scale?"])])
    analyst = RequirementsAnalyst(StructuredLLM(provider, NullUsageRecorder()))

    turn = await analyst.run(
        history=[user_message("Build a food delivery app")],
        project_settings={"target_cloud": "aws"},
        round_index=0,
        max_rounds=3,
        ctx=LLMContext(workspace_id="w1", run_id="r1"),
    )

    assert isinstance(turn, AnalystTurn)
    assert turn.ready_to_confirm is False
    assert len(turn.clarifying_questions) == 1

    # The user's message was forwarded to the model, and settings + round
    # reached the system prompt.
    system, messages = provider.calls[0]
    assert messages == [LLMMessage(MessageRole.USER, "Build a food delivery app")]
    assert "target_cloud" in system
    assert "round 1 of at most 3" in system


async def test_analyst_forwards_assistant_turns_as_model_role() -> None:
    history = [
        user_message("Build a food delivery app"),
        Message(
            id="m2",
            workspace_id="w1",
            thread_id="t1",
            role=ThreadRole.ASSISTANT,
            content={"text": "What scale?"},
            run_id="r1",
            created_at=NOW,
        ),
        user_message("One million users"),
    ]
    provider = FakeLLMProvider(responses=[_turn_json(ready=True, questions=[])])
    analyst = RequirementsAnalyst(StructuredLLM(provider, NullUsageRecorder()))

    await analyst.run(
        history=history,
        project_settings={},
        round_index=1,
        max_rounds=3,
        ctx=LLMContext(workspace_id="w1", run_id="r1"),
    )

    _, messages = provider.calls[0]
    assert [m.role for m in messages] == [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.USER]
