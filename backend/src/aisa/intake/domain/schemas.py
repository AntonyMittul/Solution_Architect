"""Typed contracts for the requirements_analyst agent (doc 07).

These Pydantic models are the agent's validated output schema and the canonical
shape of the stored requirements document. Pydantic is permitted in the domain
(it is our type-safety layer, not an I/O framework)."""

from pydantic import BaseModel, Field


class ClarifyingQuestion(BaseModel):
    id: str = Field(description="Stable short id, e.g. 'q1'")
    question: str
    why: str = Field(description="Why this matters for the design")


class RequirementsContent(BaseModel):
    schema_version: int = 1
    summary: str = Field(description="One-paragraph restatement of the product")
    goals: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(
        default_factory=list, description="Assumptions made where the user was silent"
    )
    open_questions: list[str] = Field(default_factory=list)


class AnalystTurn(BaseModel):
    """One turn of the requirements analyst."""

    assistant_message: str = Field(description="Conversational reply shown to the user")
    requirements: RequirementsContent
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list)
    ready_to_confirm: bool = Field(
        description="True when requirements are complete enough to confirm"
    )
