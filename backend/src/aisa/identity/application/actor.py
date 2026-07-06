from aisa.identity.application.ports import MembershipRepository, UserRepository
from aisa.shared.authz import Actor
from aisa.shared.errors import NotFoundError


class ResolveActor:
    """Load the acting user's membership in a workspace.

    Raises NotFoundError (not 403) for non-members so outsiders cannot
    probe which workspace ids exist.
    """

    def __init__(self, memberships: MembershipRepository, users: UserRepository) -> None:
        self._memberships = memberships
        self._users = users

    async def execute(self, user_id: str, workspace_id: str) -> Actor:
        membership = await self._memberships.get(workspace_id, user_id)
        if membership is None:
            raise NotFoundError("Workspace not found")
        user = await self._users.get(user_id)
        return Actor(
            user_id=user_id,
            workspace_id=workspace_id,
            role=membership.role,
            email_verified=user.email_verified,
        )
