import re
from dataclasses import dataclass

from aisa.artifacts.application.ports import ArtifactRepository
from aisa.artifacts.domain.models import ArtifactType
from aisa.exports.domain.bundle import assemble_files, build_zip
from aisa.intake.application.ports import RequirementRepository
from aisa.projects.application.ports import ProjectRepository
from aisa.shared.authz import Actor, Permission
from aisa.shared.errors import NotFoundError

_SLUG = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG.sub("-", name.lower()).strip("-")[:48] or "project"


@dataclass(frozen=True)
class ExportResult:
    filename: str
    data: bytes


class BuildProjectExport:
    """Bundle a project's latest artifacts + requirements into a ZIP."""

    def __init__(
        self,
        artifacts: ArtifactRepository,
        requirements: RequirementRepository,
        projects: ProjectRepository,
    ) -> None:
        self._artifacts = artifacts
        self._requirements = requirements
        self._projects = projects

    async def execute(self, actor: Actor, project_id: str) -> ExportResult:
        actor.require(Permission.PROJECT_READ)
        items = await self._artifacts.list_latest(actor.workspace_id, project_id)
        contents: dict[ArtifactType, dict[str, object]] = {
            artifact.type: version.content for artifact, version in items if version is not None
        }
        if not contents:
            raise NotFoundError("Generate a blueprint before exporting")

        requirement = await self._requirements.latest(actor.workspace_id, project_id)
        project = await self._projects.get(actor.workspace_id, project_id)

        files = assemble_files(contents, requirement.content if requirement else None)
        return ExportResult(
            filename=f"{_slugify(project.name)}-blueprint.zip", data=build_zip(files)
        )
