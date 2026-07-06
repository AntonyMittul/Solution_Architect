import io
import zipfile

from aisa.artifacts.domain.models import ArtifactType
from aisa.exports.domain import render

Content = dict[str, object]


def assemble_files(
    artifacts: dict[ArtifactType, Content], requirements: Content | None
) -> dict[str, str]:
    """Map export path -> text for the artifacts that exist."""
    files: dict[str, str] = {}

    if requirements is not None:
        files["requirements.md"] = render.render_requirements_md(requirements)

    design = artifacts.get(ArtifactType.DESIGN_DOC)
    if design is not None:
        files["README.md"] = str(design.get("markdown", "")) or "# Design document\n"

    if ArtifactType.ARCHITECTURE_DOC in artifacts:
        files["architecture.md"] = render.render_architecture_md(
            artifacts[ArtifactType.ARCHITECTURE_DOC]
        )
    if ArtifactType.TECH_STACK in artifacts:
        files["tech-stack.md"] = render.render_tech_stack_md(artifacts[ArtifactType.TECH_STACK])
    if ArtifactType.API_SPEC in artifacts:
        files["api/endpoints.md"] = render.render_api_md(artifacts[ArtifactType.API_SPEC])
        files["api/openapi.json"] = render.render_openapi_json(artifacts[ArtifactType.API_SPEC])
    if ArtifactType.DB_SCHEMA in artifacts:
        files["database/schema.sql"] = render.render_db_schema_sql(
            artifacts[ArtifactType.DB_SCHEMA]
        )
        files["database/schema.md"] = render.render_db_schema_md(artifacts[ArtifactType.DB_SCHEMA])
    if ArtifactType.DIAGRAM in artifacts:
        files["diagram/architecture.mmd"] = render.render_diagram_mermaid(
            artifacts[ArtifactType.DIAGRAM]
        )
    if ArtifactType.COST_ESTIMATE in artifacts:
        files["costs.md"] = render.render_cost_md(artifacts[ArtifactType.COST_ESTIMATE])

    return files


def build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return buffer.getvalue()
