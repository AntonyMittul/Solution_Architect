from datetime import UTC, datetime, timedelta

import jwt
import structlog
from argon2 import PasswordHasher as Argon2
from argon2.exceptions import VerifyMismatchError

from aisa.shared.errors import UnauthorizedError

logger = structlog.get_logger(__name__)


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._argon2 = Argon2()  # argon2id with library-recommended parameters

    def hash(self, password: str) -> str:
        return self._argon2.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._argon2.verify(password_hash, password)
        except VerifyMismatchError:
            return False


class JwtAccessTokenCodec:
    """Short-lived stateless access tokens (HS256)."""

    def __init__(self, secret: str, ttl: timedelta) -> None:
        self._secret = secret
        self._ttl = ttl

    def issue(self, user_id: str) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {"sub": user_id, "iat": now, "exp": now + self._ttl, "type": "access"},
            self._secret,
            algorithm="HS256",
        )

    def verify(self, token: str) -> str:
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid or expired access token") from exc
        if claims.get("type") != "access" or "sub" not in claims:
            raise UnauthorizedError("Invalid access token")
        return str(claims["sub"])


class LoggingEmailSender:
    """Dev/test adapter: logs instead of sending. Real SMTP lands with the
    notifications module (roadmap M4)."""

    async def send_verification(self, email: str, token: str) -> None:
        logger.info("email.verification", to=email, token=token)
