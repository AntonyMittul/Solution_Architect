import pytest

from aisa.shared.authz import Actor, Permission, Role
from aisa.shared.errors import ForbiddenError

# The doc-06 authorization matrix, as data.
MATRIX: list[tuple[Role, Permission, bool]] = [
    (Role.VIEWER, Permission.PROJECT_READ, True),
    (Role.VIEWER, Permission.PROJECT_WRITE, False),
    (Role.VIEWER, Permission.RUN_TRIGGER, False),
    (Role.VIEWER, Permission.MEMBER_MANAGE, False),
    (Role.MEMBER, Permission.PROJECT_READ, True),
    (Role.MEMBER, Permission.PROJECT_WRITE, True),
    (Role.MEMBER, Permission.RUN_TRIGGER, True),
    (Role.MEMBER, Permission.MEMBER_MANAGE, False),
    (Role.MEMBER, Permission.WORKSPACE_MANAGE, False),
    (Role.ADMIN, Permission.PROJECT_WRITE, True),
    (Role.ADMIN, Permission.MEMBER_MANAGE, True),
    (Role.ADMIN, Permission.WORKSPACE_MANAGE, True),
    (Role.ADMIN, Permission.WORKSPACE_DELETE, False),
    (Role.OWNER, Permission.MEMBER_MANAGE, True),
    (Role.OWNER, Permission.WORKSPACE_DELETE, True),
]


def make_actor(role: Role) -> Actor:
    return Actor(user_id="u1", workspace_id="w1", role=role, email_verified=True)


@pytest.mark.parametrize(("role", "permission", "allowed"), MATRIX)
def test_rbac_matrix(role: Role, permission: Permission, allowed: bool) -> None:
    actor = make_actor(role)
    assert actor.can(permission) is allowed
    if allowed:
        actor.require(permission)  # must not raise
    else:
        with pytest.raises(ForbiddenError):
            actor.require(permission)


def test_every_role_has_a_permission_set_defined() -> None:
    from aisa.shared.authz import ROLE_PERMISSIONS

    assert set(ROLE_PERMISSIONS) == set(Role)
