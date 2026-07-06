import io
import json
import zipfile

import sqlglot

from aisa.artifacts.domain.models import ArtifactType
from aisa.exports.domain.bundle import assemble_files, build_zip
from aisa.exports.domain.render import (
    render_db_schema_sql,
    render_diagram_mermaid,
    render_openapi_json,
)

API_CONTENT = {
    "title": "Orders API",
    "version": "1.0.0",
    "endpoints": [
        {"method": "GET", "path": "/orders", "summary": "list orders"},
        {"method": "POST", "path": "/orders", "summary": "create order"},
    ],
}
DB_CONTENT = {
    "tables": [
        {
            "name": "orders",
            "columns": [
                {"name": "id", "type": "UUID", "nullable": False},
                {"name": "total", "type": "NUMERIC", "nullable": True},
            ],
            "primary_key": ["id"],
        }
    ]
}
DIAGRAM_CONTENT = {
    "nodes": [
        {"id": "api", "label": "API", "type": "service"},
        {"id": "db", "label": "DB", "type": "datastore"},
    ],
    "edges": [{"source": "api", "target": "db", "label": "reads/writes"}],
}


def test_openapi_json_is_valid_and_has_paths() -> None:
    doc = json.loads(render_openapi_json(API_CONTENT))
    assert doc["openapi"] == "3.1.0"
    assert doc["info"]["title"] == "Orders API"
    assert set(doc["paths"]["/orders"]) == {"get", "post"}


def test_db_schema_sql_parses() -> None:
    ddl = render_db_schema_sql(DB_CONTENT)
    assert 'CREATE TABLE "orders"' in ddl
    sqlglot.parse(ddl, read="postgres")  # raises if invalid


def test_diagram_mermaid_has_nodes_and_edges() -> None:
    mermaid = render_diagram_mermaid(DIAGRAM_CONTENT)
    assert mermaid.startswith("graph LR")
    assert 'api["API"]' in mermaid
    assert "api -->|reads/writes| db" in mermaid


def test_assemble_and_zip_contains_expected_files() -> None:
    files = assemble_files(
        {
            ArtifactType.DESIGN_DOC: {"markdown": "# Design\nhello"},
            ArtifactType.API_SPEC: API_CONTENT,
            ArtifactType.DB_SCHEMA: DB_CONTENT,
            ArtifactType.DIAGRAM: DIAGRAM_CONTENT,
        },
        requirements={"summary": "an app", "goals": ["scale"]},
    )
    assert "README.md" in files
    assert "requirements.md" in files
    assert "api/openapi.json" in files
    assert "database/schema.sql" in files

    data = build_zip(files)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert "README.md" in names
        assert "database/schema.sql" in names
        assert archive.read("README.md").decode().startswith("# Design")


def test_empty_artifacts_still_assembles_requirements_only() -> None:
    files = assemble_files({}, requirements={"summary": "x"})
    assert set(files) == {"requirements.md"}
