"""Typed content schemas for each blueprint artifact (agent outputs)."""

from pydantic import BaseModel, Field


class Component(BaseModel):
    name: str
    type: str = Field(description="service | datastore | queue | external | client")
    responsibility: str


class Decision(BaseModel):
    decision: str
    rationale: str


class ArchitectureDesign(BaseModel):
    overview: str = ""
    components: list[Component] = Field(default_factory=list)
    data_flows: list[str] = Field(default_factory=list)
    key_decisions: list[Decision] = Field(default_factory=list)


class TechChoice(BaseModel):
    layer: str
    choice: str
    alternatives: list[str] = Field(default_factory=list)
    rationale: str


class TechStackRecommendation(BaseModel):
    choices: list[TechChoice] = Field(default_factory=list)


class Endpoint(BaseModel):
    method: str = Field(description="GET | POST | PUT | PATCH | DELETE")
    path: str
    summary: str


class ApiSpec(BaseModel):
    title: str = "API"
    version: str = "1.0.0"
    endpoints: list[Endpoint] = Field(default_factory=list)


class Column(BaseModel):
    name: str
    type: str = Field(description="PostgreSQL type, e.g. TEXT, INTEGER, TIMESTAMPTZ")
    nullable: bool = True


class Table(BaseModel):
    name: str
    columns: list[Column] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)


class DbSchema(BaseModel):
    tables: list[Table] = Field(default_factory=list)


class DiagramNode(BaseModel):
    id: str
    label: str
    type: str = "service"


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class DiagramSpec(BaseModel):
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class CostLineItem(BaseModel):
    service: str
    monthly_low: float = 0.0
    monthly_expected: float = 0.0
    monthly_high: float = 0.0
    notes: str = ""


class CostEstimate(BaseModel):
    currency: str = "USD"
    line_items: list[CostLineItem] = Field(default_factory=list)
    pricing_note: str = ""


class ConsistencyIssue(BaseModel):
    artifact: str
    description: str


class ConsistencyReport(BaseModel):
    is_consistent: bool = True
    issues: list[ConsistencyIssue] = Field(default_factory=list)


class DesignDocument(BaseModel):
    markdown: str = ""
