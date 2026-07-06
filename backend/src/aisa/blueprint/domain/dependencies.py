"""The blueprint artifact dependency graph, used for staleness propagation and
recorded as edges when artifacts are produced."""

from aisa.artifacts.domain.models import ArtifactType as T

ARTIFACT_DEPENDENCIES: dict[T, list[T]] = {
    T.ARCHITECTURE_DOC: [],
    T.DIAGRAM: [T.ARCHITECTURE_DOC],
    T.TECH_STACK: [T.ARCHITECTURE_DOC],
    T.API_SPEC: [T.ARCHITECTURE_DOC],
    T.DB_SCHEMA: [T.ARCHITECTURE_DOC, T.API_SPEC],
    T.COST_ESTIMATE: [T.ARCHITECTURE_DOC, T.TECH_STACK],
    T.DESIGN_DOC: [
        T.ARCHITECTURE_DOC,
        T.DIAGRAM,
        T.TECH_STACK,
        T.API_SPEC,
        T.DB_SCHEMA,
        T.COST_ESTIMATE,
    ],
}

# Which agent produces each artifact (recorded in provenance).
ARTIFACT_AGENT: dict[T, str] = {
    T.ARCHITECTURE_DOC: "solution_designer_v1",
    T.TECH_STACK: "tech_stack_recommender_v1",
    T.API_SPEC: "api_designer_v1",
    T.DB_SCHEMA: "data_modeler_v1",
    T.DIAGRAM: "diagram_generator_v1",
    T.COST_ESTIMATE: "cost_estimator_v1",
    T.DESIGN_DOC: "docs_writer_v1",
}

# State key in the graph -> artifact type.
STATE_KEY_TO_TYPE: dict[str, T] = {
    "architecture": T.ARCHITECTURE_DOC,
    "tech_stack": T.TECH_STACK,
    "api_spec": T.API_SPEC,
    "db_schema": T.DB_SCHEMA,
    "diagram": T.DIAGRAM,
    "cost_estimate": T.COST_ESTIMATE,
    "design_doc": T.DESIGN_DOC,
}
