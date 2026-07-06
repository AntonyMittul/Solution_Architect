import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import structlog

from aisa.identity.application.ports import (
    EmailSender,
    MembershipRepository,
    PasswordHasher,
    UserRepository,
    VerificationTokenRepository,
    WorkspaceRepository,
)
from aisa.identity.application.tokens import TokenPair, TokenService
from aisa.identity.domain.models import (
    Membership,
    Role,
    User,
    Workspace,
    WorkspaceKind,
    make_slug,
)
from aisa.shared.audit import AuditEntry, AuditLogger
from aisa.shared.clock import Clock
from aisa.shared.errors import ConflictError, DomainValidationError, UnauthorizedError

logger = structlog.get_logger(__name__)

MIN_PASSWORD_LENGTH = 10


@dataclass(frozen=True)
class RegistrationResult:
    user: User
    workspace: Workspace
    verification_token: str  # plain token; exposed to the user only via email (or dev mode)


class RegisterUser:
    def __init__(
        self,
        users: UserRepository,
        workspaces: WorkspaceRepository,
        memberships: MembershipRepository,
        verification_tokens: VerificationTokenRepository,
        hasher: PasswordHasher,
        email_sender: EmailSender,
        audit: AuditLogger,
        clock: Clock,
        id_factory: Callable[[], str],
        verification_ttl: timedelta,
    ) -> None:
        self._users = users
        self._workspaces = workspaces
        self._memberships = memberships
        self._verification_tokens = verification_tokens
        self._hasher = hasher
        self._email_sender = email_sender
        self._audit = audit
        self._clock = clock
        self._id_factory = id_factory
        self._verification_ttl = verification_ttl

    async def execute(self, email: str, password: str, name: str) -> RegistrationResult:
        email = email.strip().lower()
        if len(password) < MIN_PASSWORD_LENGTH:
            raise DomainValidationError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        if not name.strip():
            raise DomainValidationError("Name must not be empty")
        if await self._users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")

        now = self._clock.now()
        user = User(
            id=self._id_factory(),
            email=email,
            name=name.strip(),
            email_verified=False,
            created_at=now,
            updated_at=now,
        )
        await self._users.add(user, self._hasher.hash(password))

        workspace = Workspace.create(
            workspace_id=self._id_factory(),
            slug=make_slug(email.split("@")[0], user.id),
            name=f"{user.name}'s workspace",
            kind=WorkspaceKind.PERSONAL,
            now=now,
        )
        await self._workspaces.add(workspace)
        await self._memberships.add(
            Membership(
                id=self._id_factory(),
                workspace_id=workspace.id,
                user_id=user.id,
                role=Role.OWNER,
            )
        )

        token = secrets.token_urlsafe(32)
        await self._verification_tokens.add(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=now + self._verification_ttl,
        )
        await self._email_sender.send_verification(user.email, token)
        await self._audit.record(
            AuditEntry(actor=f"user:{user.id}", action="auth.registered", target=user.email)
        )
        logger.info("auth.registered", user_id=user.id)
        return RegistrationResult(user=user, workspace=workspace, verification_token=token)


class VerifyEmail:
    def __init__(
        self,
        users: UserRepository,
        verification_tokens: VerificationTokenRepository,
        audit: AuditLogger,
        clock: Clock,
    ) -> None:
        self._users = users
        self._verification_tokens = verification_tokens
        self._audit = audit
        self._clock = clock

    async def execute(self, token: str) -> User:
        now = self._clock.now()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        user_id = await self._verification_tokens.consume(token_hash, now)
        if user_id is None:
            raise DomainValidationError("Invalid or expired verification token")
        user = await self._users.get(user_id)
        user.verify_email(now)
        await self._users.save(user)
        await self._audit.record(AuditEntry(actor=f"user:{user.id}", action="auth.email_verified"))
        return user


class LoginUser:
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenService,
        audit: AuditLogger,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._audit = audit

    async def execute(self, email: str, password: str) -> TokenPair:
        found = await self._users.get_by_email(email.strip().lower())
        # Same error for unknown email and wrong password: no account enumeration.
        if found is None:
            raise UnauthorizedError("Invalid email or password")
        user, password_hash = found
        if password_hash is None or not self._hasher.verify(password, password_hash):
            raise UnauthorizedError("Invalid email or password")
        pair = await self._tokens.issue_pair(user.id)
        await self._audit.record(AuditEntry(actor=f"user:{user.id}", action="auth.login"))
        return pair


class GetCurrentUser:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, user_id: str) -> User:
        return await self._users.get(user_id)
