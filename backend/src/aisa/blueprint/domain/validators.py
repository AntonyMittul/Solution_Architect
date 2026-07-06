"""Deterministic hard-gate validators for blueprint artifacts (doc 12 §3).

Each returns a list of human-readable problems (empty = valid)."""

import sqlglot

from aisa.blueprint.domain.ddl import render_ddl
from aisa.blueprint.domain.schemas import ApiSpec, DbSchema, DiagramSpec

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def validate_diagram(spec: DiagramSpec) -> list[str]:
    node_ids = {node.id for node in spec.nodes}
    problems: list[str] = []
    for edge in spec.edges:
        if edge.source not in node_ids:
            problems.append(f"diagram edge source '{edge.source}' is not a node")
        if edge.target not in node_ids:
            problems.append(f"diagram edge target '{edge.target}' is not a node")
    return problems


def validate_api_spec(spec: ApiSpec) -> list[str]:
    problems: list[str] = []
    for endpoint in spec.endpoints:
        if endpoint.method.upper() not in HTTP_METHODS:
            problems.append(f"invalid HTTP method '{endpoint.method}' for {endpoint.path}")
        if not endpoint.path.startswith("/"):
            problems.append(f"endpoint path '{endpoint.path}' must start with '/'")
    return problems


def validate_db_schema(schema: DbSchema) -> list[str]:
    ddl = render_ddl(schema)
    if not ddl.strip():
        return []
    try:
        sqlglot.parse(ddl, read="postgres")
    except Exception as exc:  # sqlglot raises ParseError subclasses
        return [f"DDL does not parse: {exc}"]
    return []
