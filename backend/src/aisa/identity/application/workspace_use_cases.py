from collections.abc import Callable

from aisa.identity.application.ports import (
    MembershipRepository,
    UserRepository,
    WorkspaceRepository,
)
from aisa.identity.domain.models import (
    Membership,
    Role,
    User,
    Workspace,
    WorkspaceKind,
    make_slug,
)
from aisa.shared.audit import AuditEntry, AuditLogger
from aisa.shared.authz import Actor, Permission
from aisa.shared.clock import Clock
from aisa.shared.errors import ConflictError, DomainValidationError, NotFoundError

ASSIGNABLE_ROLES = frozenset({Role.ADMIN, Role.MEMBER, Role.VIEWER})


class ListMyWorkspaces:
    def __init__(self, workspaces: WorkspaceRepository) -> None:
        self._workspaces = workspaces

    async def execute(self, user_id: str) -> list[tuple[Workspace, Role]]:
        return await self._workspaces.list_for_user(user_id)


class CreateWorkspace:
    def __init__(
        self,
        workspaces: WorkspaceRepository,
        memberships: MembershipRepository,
        audit: AuditLogger,
        clock: Clock,
        id_factory: Callable[[], str],
    ) -> None:
        self._workspaces = workspaces
        self._memberships = memberships
        self._audit = audit
        self._clock = clock
        self._id_factory = id_factory

    async def execute(self, user_id: str, name: str) -> Workspace:
        workspace_id = self._id_factory()
        workspace = Workspace.create(
            workspace_id=workspace_id,
            slug=make_slug(name, workspace_id),
            name=name,
            kind=WorkspaceKind.TEAM,
            now=self._clock.now(),
        )
        await self._workspaces.add(workspace)
        await self._memberships.add(
            Membership(
                id=self._id_factory(),
                workspace_id=workspace.id,
                user_id=user_id,
                role=Role.OWNER,
            )
        )
        await self._audit.record(
            AuditEntry(
                actor=f"user:{user_id}",
                action="workspace.created",
                workspace_id=workspace.id,
                target=workspace.slug,
            )
        )
        return workspace


class ListMembers:
    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    async def execute(self, actor: Actor) -> list[tuple[Membership, User]]:
        # Any member of the workspace (including viewers) may see the roster.
        return await self._memberships.list_for_workspace(actor.workspace_id)


class InviteMember:
    def __init__(
        self,
        workspaces: WorkspaceRepository,
        memberships: MembershipRepository,
        users: UserRepository,
        audit: AuditLogger,
        id_factory: Callable[[], str],
    ) -> None:
        self._workspaces = workspaces
        self._memberships = memberships
        self._users = users
        self._audit = audit
        self._id_factory = id_factory

    async def execute(self, actor: Actor, email: str, role: Role) -> Membership:
        actor.require(Permission.MEMBER_MANAGE)
        if role not in ASSIGNABLE_ROLES:
            raise DomainValidationError(f"Role '{role}' cannot be assigned")
        workspace = await self._workspaces.get(actor.workspace_id)
        if workspace.kind is WorkspaceKind.PERSONAL:
            raise ConflictError("Personal workspaces cannot have additional members")
        found = await self._users.get_by_email(email.strip().lower())
        if found is None:
            raise NotFoundError("No account exists for that email")
        user, _ = found
        if await self._memberships.get(actor.workspace_id, user.id) is not None:
            raise ConflictError("User is already a member of this workspace")

        membership = Membership(
            id=self._id_factory(),
            workspace_id=actor.workspace_id,
            user_id=user.id,
            role=role,
        )
        await self._memberships.add(membership)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="member.invited",
                workspace_id=actor.workspace_id,
                target=f"user:{user.id}",
                metadata={"role": role.value},
            )
        )
        return membership


class ChangeMemberRole:
    def __init__(self, memberships: MembershipRepository, audit: AuditLogger) -> None:
        self._memberships = memberships
        self._audit = audit

    async def execute(self, actor: Actor, target_user_id: str, role: Role) -> Membership:
        actor.require(Permission.MEMBER_MANAGE)
        if role not in ASSIGNABLE_ROLES:
            raise DomainValidationError(f"Role '{role}' cannot be assigned")
        membership = await self._memberships.get(actor.workspace_id, target_user_id)
        if membership is None:
            raise NotFoundError("Member not found in this workspace")
        if membership.role is Role.OWNER:
            raise ConflictError("The workspace owner's role cannot be changed")
        membership.role = role
        await self._memberships.save(membership)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="member.role_changed",
                workspace_id=actor.workspace_id,
                target=f"user:{target_user_id}",
                metadata={"role": role.value},
            )
        )
        return membership


class RemoveMember:
    def __init__(self, memberships: MembershipRepository, audit: AuditLogger) -> None:
        self._memberships = memberships
        self._audit = audit

    async def execute(self, actor: Actor, target_user_id: str) -> None:
        actor.require(Permission.MEMBER_MANAGE)
        membership = await self._memberships.get(actor.workspace_id, target_user_id)
        if membership is None:
            raise NotFoundError("Member not found in this workspace")
        if membership.role is Role.OWNER:
            raise ConflictError("The workspace owner cannot be removed")
        await self._memberships.remove(membership.id)
        await self._audit.record(
            AuditEntry(
                actor=actor.audit_ref,
                action="member.removed",
                workspace_id=actor.workspace_id,
                target=f"user:{target_user_id}",
            )
        )
