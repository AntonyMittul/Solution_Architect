from collections.abc import Callable

from aisa.projects.application.ports import ProjectRepository
from aisa.projects.domain.project import Project, ProjectStatus
from aisa.shared.audit import AuditEntry, AuditLogger
from aisa.shared.authz import Actor, Permission
from aisa.shared.clock import Clock
from aisa.shared.errors import ForbiddenError


class CreateProject:
    def __init__(
        self,
        projects: ProjectRepository,
        audit: AuditLogger,
        clock: Clock,
        id_factory: Callable[[], str],
    ) -> None:
        self._projects = projects
        self._audit = audit
        self._clock = clock
        self._id_factory = id_factory

    async def execute(
        self,
        actor: Actor,
        name: str,
        description: str | None,
        settings: dict[str, object],
    ) -> Project:
        actor.require(Permission.PROJECT_WRITE)
        if not actor.email_verified:
            raise ForbiddenError("Verify your email address before creating projects")
        project = Project.create(
            project_id=self._id_factory(),
            workspace_id=actor.workspace_id,
            name=name,
            description=description,
            settings=settings,
            created_by=actor.user_id,
            now=self._clock.now(),
        )
        await self._projects.add(project)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="project.created",
                workspace_id=actor.workspace_id,
                target=f"project:{project.id}",
            )
        )
        return project


class ListProjects:
    def __init__(self, projects: ProjectRepository) -> None:
        self._projects = projects

    async def execute(self, actor: Actor) -> list[Project]:
        actor.require(Permission.PROJECT_READ)
        return await self._projects.list_active(actor.workspace_id)


class GetProject:
    def __init__(self, projects: ProjectRepository) -> None:
        self._projects = projects

    async def execute(self, actor: Actor, project_id: str) -> Project:
        actor.require(Permission.PROJECT_READ)
        return await self._projects.get(actor.workspace_id, project_id)


class UpdateProject:
    def __init__(self, projects: ProjectRepository, clock: Clock) -> None:
        self._projects = projects
        self._clock = clock

    async def execute(
        self,
        actor: Actor,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        status: ProjectStatus | None = None,
        settings: dict[str, object] | None = None,
    ) -> Project:
        actor.require(Permission.PROJECT_WRITE)
        now = self._clock.now()
        project = await self._projects.get(actor.workspace_id, project_id)
        if name is not None:
            project.rename(name, now)
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        if settings is not None:
            project.settings = settings
        project.updated_at = now
        await self._projects.save(project)
        return project


class DeleteProject:
    def __init__(self, projects: ProjectRepository, audit: AuditLogger, clock: Clock) -> None:
        self._projects = projects
        self._audit = audit
        self._clock = clock

    async def execute(self, actor: Actor, project_id: str) -> None:
        actor.require(Permission.PROJECT_WRITE)
        project = await self._projects.get(actor.workspace_id, project_id)
        project.soft_delete(self._clock.now())
        await self._projects.save(project)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="project.deleted",
                workspace_id=actor.workspace_id,
                target=f"project:{project.id}",
            )
        )


class RestoreProject:
    def __init__(self, projects: ProjectRepository, audit: AuditLogger, clock: Clock) -> None:
        self._projects = projects
        self._audit = audit
        self._clock = clock

    async def execute(self, actor: Actor, project_id: str) -> Project:
        actor.require(Permission.PROJECT_WRITE)
        project = await self._projects.get(actor.workspace_id, project_id, include_deleted=True)
        project.restore(self._clock.now())
        await self._projects.save(project)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="project.restored",
                workspace_id=actor.workspace_id,
                target=f"project:{project.id}",
            )
        )
        return project
