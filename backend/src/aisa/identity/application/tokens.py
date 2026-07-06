import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import structlog

from aisa.identity.application.ports import (
    AccessTokenCodec,
    RefreshTokenRecord,
    RefreshTokenRepository,
)
from aisa.shared.clock import Clock
from aisa.shared.errors import UnauthorizedError

logger = structlog.get_logger(__name__)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    user_id: str


class TokenService:
    """Access JWT + rotating opaque refresh tokens (stored hashed).

    Rotation model: each refresh token is single-use and belongs to a family.
    Presenting an already-used token is treated as theft — the whole family
    is revoked (doc 09 §1: refresh reuse detection kills the family).
    """

    def __init__(
        self,
        refresh_repository: RefreshTokenRepository,
        access_codec: AccessTokenCodec,
        clock: Clock,
        id_factory: Callable[[], str],
        refresh_ttl: timedelta,
    ) -> None:
        self._refresh_repository = refresh_repository
        self._access_codec = access_codec
        self._clock = clock
        self._id_factory = id_factory
        self._refresh_ttl = refresh_ttl

    async def issue_pair(self, user_id: str, family_id: str | None = None) -> TokenPair:
        refresh_plain = secrets.token_urlsafe(48)
        record = RefreshTokenRecord(
            id=self._id_factory(),
            user_id=user_id,
            family_id=family_id or self._id_factory(),
            token_hash=_hash(refresh_plain),
            expires_at=self._clock.now() + self._refresh_ttl,
        )
        await self._refresh_repository.add(record)
        return TokenPair(
            access_token=self._access_codec.issue(user_id),
            refresh_token=refresh_plain,
            user_id=user_id,
        )

    async def rotate(self, refresh_plain: str) -> TokenPair:
        now = self._clock.now()
        record = await self._refresh_repository.get_by_hash(_hash(refresh_plain))
        if record is None or record.revoked_at is not None:
            raise UnauthorizedError("Invalid refresh token")
        if record.used_at is not None:
            # Reuse of a rotated token: assume the family is compromised.
            await self._refresh_repository.revoke_family(record.family_id, now)
            logger.warning(
                "auth.refresh_reuse_detected", user_id=record.user_id, family=record.family_id
            )
            raise UnauthorizedError("Invalid refresh token")
        if record.expires_at <= now:
            raise UnauthorizedError("Refresh token expired")

        await self._refresh_repository.mark_used(record.id, now)
        return await self.issue_pair(record.user_id, family_id=record.family_id)

    async def revoke(self, refresh_plain: str) -> None:
        record = await self._refresh_repository.get_by_hash(_hash(refresh_plain))
        if record is not None:
            await self._refresh_repository.revoke_family(record.family_id, self._clock.now())
