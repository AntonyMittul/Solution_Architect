"""HTTP-edge auth dependencies. Live in platform (not a feature module)
because request authentication is a cross-cutting concern of the app shell."""

from typing import Annotated

from fastapi import Depends, Request

from aisa.platform.container import Container
from aisa.shared.authz import Actor
from aisa.shared.errors import UnauthorizedError

ACCESS_COOKIE = "aisa_access"
REFRESH_COOKIE = "aisa_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def get_current_user_id(
    request: Request, container: Annotated[Container, Depends(get_container)]
) -> str:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise UnauthorizedError("Not authenticated")
    return container.access_codec.verify(token)


CurrentUserId = Annotated[str, Depends(get_current_user_id)]


async def get_actor(
    workspace_id: str,
    user_id: CurrentUserId,
    container: Annotated[Container, Depends(get_container)],
) -> Actor:
    return await container.resolve_actor.execute(user_id=user_id, workspace_id=workspace_id)


CurrentActor = Annotated[Actor, Depends(get_actor)]
ContainerDep = Annotated[Container, Depends(get_container)]
