from datetime import datetime

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, EmailStr

from aisa.identity.application.tokens import TokenPair
from aisa.identity.domain.models import User
from aisa.platform.api.deps import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    ContainerDep,
    CurrentUserId,
)
from aisa.shared.errors import UnauthorizedError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    email_verified: bool
    created_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            email_verified=user.email_verified,
            created_at=user.created_at,
        )


class RegisterResponse(BaseModel):
    user: UserResponse
    workspace_id: str
    # Dev convenience only: in deployed envs the token travels by email alone.
    verification_token: str | None = None


def _set_auth_cookies(response: Response, pair: TokenPair, container: ContainerDep) -> None:
    settings = container.settings
    response.set_cookie(
        ACCESS_COOKIE,
        pair.access_token,
        max_age=settings.access_token_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=not settings.is_dev,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        samesite="lax",
        secure=not settings.is_dev,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, container: ContainerDep) -> RegisterResponse:
    result = await container.register_user.execute(
        email=body.email, password=body.password, name=body.name
    )
    return RegisterResponse(
        user=UserResponse.from_domain(result.user),
        workspace_id=result.workspace.id,
        verification_token=result.verification_token if container.settings.is_dev else None,
    )


@router.post("/verify")
async def verify_email(body: VerifyEmailRequest, container: ContainerDep) -> UserResponse:
    user = await container.verify_email.execute(body.token)
    return UserResponse.from_domain(user)


class ResendVerificationResponse(BaseModel):
    sent: bool
    # Populated only in dev (no SMTP); lets the UI complete verification in-app.
    verification_token: str | None = None


@router.post("/resend-verification")
async def resend_verification(
    user_id: CurrentUserId, container: ContainerDep
) -> ResendVerificationResponse:
    token = await container.resend_verification.execute(user_id)
    return ResendVerificationResponse(
        sent=True, verification_token=token if container.settings.is_dev else None
    )


@router.post("/login")
async def login(body: LoginRequest, response: Response, container: ContainerDep) -> UserResponse:
    pair = await container.login_user.execute(email=body.email, password=body.password)
    _set_auth_cookies(response, pair, container)
    user = await container.get_current_user.execute(pair.user_id)
    return UserResponse.from_domain(user)


@router.post("/refresh")
async def refresh(request: Request, response: Response, container: ContainerDep) -> dict[str, str]:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise UnauthorizedError("No refresh token")
    try:
        pair = await container.token_service.rotate(refresh_token)
    except UnauthorizedError:
        _clear_auth_cookies(response)
        raise
    _set_auth_cookies(response, pair, container)
    return {"user_id": pair.user_id}


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, container: ContainerDep) -> None:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        await container.token_service.revoke(refresh_token)
    _clear_auth_cookies(response)


@router.get("/me")
async def me(user_id: CurrentUserId, container: ContainerDep) -> UserResponse:
    user = await container.get_current_user.execute(user_id)
    return UserResponse.from_domain(user)
