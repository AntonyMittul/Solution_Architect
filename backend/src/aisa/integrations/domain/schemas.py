from pydantic import BaseModel, Field


class PlannedToolCall(BaseModel):
    server_id: str = Field(description="id of a server from the provided catalog")
    tool_name: str = Field(description="an allowlisted tool on that server")
    arguments: dict[str, str] = Field(default_factory=dict)
    rationale: str = Field(description="why this call is needed")


class ProvisioningPlanOutput(BaseModel):
    """Structured output of the provisioner agent — a plan, never an execution."""

    summary: str
    tool_calls: list[PlannedToolCall] = Field(default_factory=list)
