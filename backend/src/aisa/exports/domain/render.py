"""Pure renderers that turn artifact/requirements content into the files of an
export bundle. Each takes plain dicts (as stored) and returns text."""

import json
import re
from typing import Any

from aisa.blueprint.domain.ddl import render_ddl
from aisa.blueprint.domain.schemas import ApiSpec, DbSchema, DiagramSpec

_MERMAID_ID = re.compile(r"[^A-Za-z0-9_]")


def _mid(node_id: str) -> str:
    cleaned = _MERMAID_ID.sub("_", node_id).strip("_")
    return cleaned or "n"


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _bullets(items: list[Any]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "_None specified._"


def render_requirements_md(content: dict[str, object]) -> str:
    sections = [
        ("Goals", "goals"),
        ("Actors", "actors"),
        ("Functional requirements", "functional_requirements"),
        ("Non-functional requirements", "non_functional_requirements"),
        ("Constraints", "constraints"),
        ("Assumptions", "assumptions"),
        ("Open questions", "open_questions"),
    ]
    parts = ["# Requirements", "", str(content.get("summary", "")), ""]
    for title, key in sections:
        parts += [f"## {title}", "", _bullets(_list(content.get(key))), ""]
    return "\n".join(parts)


def render_architecture_md(content: dict[str, object]) -> str:
    parts = ["# Architecture", "", str(content.get("overview", "")), "", "## Components", ""]
    for component in _list(content.get("components")):
        parts.append(
            f"- **{component.get('name', '')}** "
            f"({component.get('type', '')}) — {component.get('responsibility', '')}"
        )
    parts += ["", "## Data flows", "", _bullets(_list(content.get("data_flows"))), ""]
    parts += ["## Key decisions", ""]
    for decision in _list(content.get("key_decisions")):
        parts.append(f"- **{decision.get('decision', '')}** — {decision.get('rationale', '')}")
    return "\n".join(parts)


def render_tech_stack_md(content: dict[str, object]) -> str:
    parts = ["# Technology stack", ""]
    for choice in _list(content.get("choices")):
        alts = ", ".join(_list(choice.get("alternatives")))
        parts += [
            f"## {choice.get('layer', '')}: {choice.get('choice', '')}",
            "",
            str(choice.get("rationale", "")),
            f"\n_Alternatives considered: {alts or 'none'}._" if alts else "",
            "",
        ]
    return "\n".join(parts)


def render_api_md(content: dict[str, object]) -> str:
    spec = ApiSpec.model_validate(content)
    parts = [f"# API — {spec.title} v{spec.version}", ""]
    for endpoint in spec.endpoints:
        parts.append(f"- `{endpoint.method.upper()} {endpoint.path}` — {endpoint.summary}")
    return "\n".join(parts)


def render_openapi_json(content: dict[str, object]) -> str:
    spec = ApiSpec.model_validate(content)
    paths: dict[str, dict[str, object]] = {}
    for endpoint in spec.endpoints:
        method = endpoint.method.lower()
        paths.setdefault(endpoint.path, {})[method] = {
            "summary": endpoint.summary,
            "responses": {"200": {"description": "OK"}},
        }
    document = {
        "openapi": "3.1.0",
        "info": {"title": spec.title, "version": spec.version},
        "paths": paths,
    }
    return json.dumps(document, indent=2)


def render_db_schema_sql(content: dict[str, object]) -> str:
    return render_ddl(DbSchema.model_validate(content))


def render_db_schema_md(content: dict[str, object]) -> str:
    schema = DbSchema.model_validate(content)
    parts = ["# Database schema", ""]
    for table in schema.tables:
        parts += [f"## {table.name}", ""]
        for column in table.columns:
            flags = []
            if not column.nullable:
                flags.append("NOT NULL")
            if column.name in table.primary_key:
                flags.append("PK")
            suffix = f" ({', '.join(flags)})" if flags else ""
            parts.append(f"- `{column.name}` {column.type}{suffix}")
        parts.append("")
    return "\n".join(parts)


def render_cost_md(content: dict[str, object]) -> str:
    currency = content.get("currency", "USD")
    parts = [
        "# Cost estimate",
        "",
        "| Service | Low | Expected | High |",
        "| --- | --- | --- | --- |",
    ]
    total = 0.0
    for item in _list(content.get("line_items")):
        expected = float(item.get("monthly_expected", 0) or 0)
        total += expected
        parts.append(
            f"| {item.get('service', '')} | {item.get('monthly_low', 0)} | "
            f"{expected} | {item.get('monthly_high', 0)} |"
        )
    parts += ["", f"**Estimated total: ~{total:,.0f} {currency}/month (expected).**"]
    note = content.get("pricing_note")
    if note:
        parts += ["", f"_{note}_"]
    return "\n".join(parts)


def render_diagram_mermaid(content: dict[str, object]) -> str:
    spec = DiagramSpec.model_validate(content)
    ids = {node.id for node in spec.nodes}
    lines = ["graph LR"]
    for node in spec.nodes:
        lines.append(f'    {_mid(node.id)}["{node.label}"]')
    for edge in spec.edges:
        if edge.source not in ids or edge.target not in ids:
            continue
        label = f"|{edge.label}|" if edge.label else ""
        lines.append(f"    {_mid(edge.source)} -->{label} {_mid(edge.target)}")
    return "\n".join(lines)
