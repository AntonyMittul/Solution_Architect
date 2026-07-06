"""The blueprint LangGraph: solution design, then a parallel fan-out of the
specialist agents, a consistency review with a bounded repair loop, and the
docs writer. LangGraph owns control flow; our agents own the LLM calls (ADR-002,
ADR-003)."""

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from aisa.blueprint.application.agents import BlueprintAgents
from aisa.blueprint.domain.schemas import (
    ApiSpec,
    ConsistencyReport,
    DbSchema,
    DiagramSpec,
)
from aisa.blueprint.domain.validators import (
    validate_api_spec,
    validate_db_schema,
    validate_diagram,
)
from aisa.llm.application.service import LLMContext

Emit = Callable[[str, dict[str, object]], Awaitable[None]]


class BlueprintState(TypedDict, total=False):
    requirements: dict[str, Any]
    settings: dict[str, Any]
    feedback: list[str]
    repair_count: int
    architecture: dict[str, Any]
    tech_stack: dict[str, Any]
    api_spec: dict[str, Any]
    db_schema: dict[str, Any]
    diagram: dict[str, Any]
    cost_estimate: dict[str, Any]
    consistency: dict[str, Any]
    design_doc: dict[str, Any]


def build_blueprint_graph(
    agents: BlueprintAgents, emit: Emit, ctx: LLMContext, max_repairs: int = 1
) -> Any:
    async def _agent(name: str, coro: Awaitable[Any]) -> Any:
        await emit("agent.started", {"agent": name})
        result = await coro
        await emit("agent.completed", {"agent": name})
        return result

    async def designer(state: BlueprintState) -> dict[str, Any]:
        design = await _agent(
            "solution_designer",
            agents.design(state["requirements"], state["settings"], state.get("feedback", []), ctx),
        )
        return {"architecture": design.model_dump()}

    # Three independent branches run in parallel. Each dependent step lives
    # inside its branch (data model needs the API; cost needs the stack), so all
    # three branches sit at the same graph depth and the reviewer barrier waits
    # for all of them (LangGraph fan-in requires matching depth).

    async def branch_api_db(state: BlueprintState) -> dict[str, Any]:
        api = await _agent("api_designer", agents.api(state["architecture"], ctx))
        db = await _agent(
            "data_modeler", agents.data_model(state["architecture"], api.model_dump(), ctx)
        )
        return {"api_spec": api.model_dump(), "db_schema": db.model_dump()}

    async def branch_stack_cost(state: BlueprintState) -> dict[str, Any]:
        stack = await _agent(
            "tech_stack_recommender",
            agents.tech_stack(state["architecture"], state["settings"], ctx),
        )
        cost = await _agent(
            "cost_estimator",
            agents.cost(state["architecture"], stack.model_dump(), state["settings"], ctx),
        )
        return {"tech_stack": stack.model_dump(), "cost_estimate": cost.model_dump()}

    async def branch_diagram(state: BlueprintState) -> dict[str, Any]:
        result = await _agent("diagram_generator", agents.diagram(state["architecture"], ctx))
        return {"diagram": result.model_dump()}

    async def reviewer(state: BlueprintState) -> dict[str, Any]:
        bundle = {
            "architecture": state["architecture"],
            "tech_stack": state["tech_stack"],
            "api_spec": state["api_spec"],
            "db_schema": state["db_schema"],
            "diagram": state["diagram"],
            "cost_estimate": state["cost_estimate"],
        }
        report = await _agent("design_reviewer", agents.review(bundle, ctx))
        issues = [i.model_dump() for i in report.issues]
        # Deterministic hard-gate validators augment the model's judgement.
        issues += [
            {"artifact": "diagram", "description": p}
            for p in validate_diagram(DiagramSpec.model_validate(state["diagram"]))
        ]
        issues += [
            {"artifact": "api_spec", "description": p}
            for p in validate_api_spec(ApiSpec.model_validate(state["api_spec"]))
        ]
        issues += [
            {"artifact": "db_schema", "description": p}
            for p in validate_db_schema(DbSchema.model_validate(state["db_schema"]))
        ]
        consistency = ConsistencyReport(is_consistent=not issues, issues=issues).model_dump()
        return {"consistency": consistency}

    async def revise(state: BlueprintState) -> dict[str, Any]:
        issues = state["consistency"]["issues"]
        feedback = [f"{i['artifact']}: {i['description']}" for i in issues]
        await emit("blueprint.revising", {"round": state.get("repair_count", 0) + 1})
        return {"repair_count": state.get("repair_count", 0) + 1, "feedback": feedback}

    async def docs(state: BlueprintState) -> dict[str, Any]:
        bundle = {
            "architecture": state["architecture"],
            "tech_stack": state["tech_stack"],
            "api_spec": state["api_spec"],
            "db_schema": state["db_schema"],
            "diagram": state["diagram"],
            "cost_estimate": state["cost_estimate"],
            "consistency": state.get("consistency", {}),
        }
        result = await _agent("docs_writer", agents.docs(bundle, ctx))
        return {"design_doc": result.model_dump()}

    def route_after_review(state: BlueprintState) -> str:
        issues = state.get("consistency", {}).get("issues", [])
        if issues and state.get("repair_count", 0) < max_repairs:
            return "revise"
        return "finish"

    graph = StateGraph(BlueprintState)
    graph.add_node("designer", designer)
    graph.add_node("branch_api_db", branch_api_db)
    graph.add_node("branch_stack_cost", branch_stack_cost)
    graph.add_node("branch_diagram", branch_diagram)
    graph.add_node("reviewer", reviewer)
    graph.add_node("revise", revise)
    graph.add_node("docs", docs)

    graph.add_edge(START, "designer")
    graph.add_edge("designer", "branch_api_db")
    graph.add_edge("designer", "branch_stack_cost")
    graph.add_edge("designer", "branch_diagram")
    graph.add_edge("branch_api_db", "reviewer")  # barrier: all three branches
    graph.add_edge("branch_stack_cost", "reviewer")
    graph.add_edge("branch_diagram", "reviewer")
    graph.add_conditional_edges(
        "reviewer", route_after_review, {"revise": "revise", "finish": "docs"}
    )
    graph.add_edge("revise", "designer")
    graph.add_edge("docs", END)
    return graph.compile()
