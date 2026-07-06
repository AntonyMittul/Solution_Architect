from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ArtifactType(StrEnum):
    ARCHITECTURE_DOC = "architecture_doc"
    TECH_STACK = "tech_stack"
    API_SPEC = "api_spec"
    DB_SCHEMA = "db_schema"
    DIAGRAM = "diagram"
    COST_ESTIMATE = "cost_estimate"
    DESIGN_DOC = "design_doc"


@dataclass
class Artifact:
    """Identity of an artifact within a project (one per type)."""

    id: str
    workspace_id: str
    project_id: str
    type: ArtifactType
    is_stale: bool


@dataclass
class ArtifactVersion:
    id: str
    workspace_id: str
    artifact_id: str
    version: int
    content: dict[str, object]
    provenance: dict[str, object]  # run_id, agent, model, source, requirements_version
    created_at: datetime
