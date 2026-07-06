import json

from aisa.blueprint.application.agents import BlueprintAgents
from aisa.blueprint.application.graph import build_blueprint_graph
from aisa.blueprint.domain.schemas import DiagramEdge, DiagramNode, DiagramSpec
from aisa.llm.application.service import LLMContext, StructuredLLM
from aisa.llm.domain.messages import LLMMessage
from aisa.llm.infrastructure.fake import FakeLLMProvider, _minimal_dict
from aisa.llm.infrastructure.usage import NullUsageRecorder

ALL_ARTIFACT_KEYS = {
    "architecture",
    "tech_stack",
    "api_spec",
    "db_schema",
    "diagram",
    "cost_estimate",
    "design_doc",
}
CTX = LLMContext(workspace_id="w1", run_id="r1")


def _events() -> tuple[list[str], object]:
    seen: list[str] = []

    async def emit(event_type: str, payload: dict[str, object]) -> None:
        seen.append(event_type)

    return seen, emit


async def test_graph_produces_all_artifacts() -> None:
    agents = BlueprintAgents(StructuredLLM(FakeLLMProvider(), NullUsageRecorder()))
    seen, emit = _events()
    graph = build_blueprint_graph(agents, emit, CTX, max_repairs=1)

    final = await graph.ainvoke(
        {"requirements": {"summary": "app"}, "settings": {}, "feedback": [], "repair_count": 0}
    )

    assert set(final) >= ALL_ARTIFACT_KEYS
    assert final["consistency"]["is_consistent"] is True
    assert final.get("repair_count", 0) == 0  # clean run, no repair loop
    # Each specialist emitted start/complete; docs ran last.
    assert seen.count("agent.started") >= 7
    assert "agent.completed" in seen


def _bad_diagram_handler(system: str, messages: list[LLMMessage], model: type) -> str:
    # Always return a diagram with a dangling edge so the deterministic validator
    # keeps flagging it; every other agent returns a valid minimal instance.
    if model is DiagramSpec:
        return DiagramSpec(
            nodes=[DiagramNode(id="api", label="API")],
            edges=[DiagramEdge(source="api", target="ghost")],
        ).model_dump_json()
    return json.dumps(_minimal_dict(model))


async def test_repair_loop_runs_and_is_bounded() -> None:
    agents = BlueprintAgents(
        StructuredLLM(FakeLLMProvider(handler=_bad_diagram_handler), NullUsageRecorder())
    )
    seen, emit = _events()
    graph = build_blueprint_graph(agents, emit, CTX, max_repairs=1)

    final = await graph.ainvoke(
        {"requirements": {}, "settings": {}, "feedback": [], "repair_count": 0}
    )

    # One repair round happened, then the cap stopped further looping.
    assert final["repair_count"] == 1
    assert "blueprint.revising" in seen
    assert final["consistency"]["issues"]  # still inconsistent, but we finished
    assert "design_doc" in final  # docs still produced
