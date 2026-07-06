from datetime import timedelta

import pytest

from aisa.identity.application.tokens import TokenService
from aisa.identity.infrastructure.security import JwtAccessTokenCodec
from aisa.shared.errors import UnauthorizedError
from aisa.shared.ids import new_id
from tests.fakes import FakeClock, FakeRefreshTokenRepository


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def repo() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()


@pytest.fixture
def service(repo: FakeRefreshTokenRepository, clock: FakeClock) -> TokenService:
    codec = JwtAccessTokenCodec("test-secret", ttl=timedelta(minutes=15))
    return TokenService(repo, codec, clock, new_id, refresh_ttl=timedelta(days=30))


async def test_issue_and_rotate_happy_path(service: TokenService) -> None:
    pair1 = await service.issue_pair("user-1")
    pair2 = await service.rotate(pair1.refresh_token)
    assert pair2.user_id == "user-1"
    assert pair2.refresh_token != pair1.refresh_token


async def test_reuse_of_rotated_token_revokes_whole_family(service: TokenService) -> None:
    pair1 = await service.issue_pair("user-1")
    pair2 = await service.rotate(pair1.refresh_token)

    with pytest.raises(UnauthorizedError):
        await service.rotate(pair1.refresh_token)  # replayed old token
    # The freshly issued token is collateral damage — the family is dead.
    with pytest.raises(UnauthorizedError):
        await service.rotate(pair2.refresh_token)


async def test_expired_refresh_token_rejected(service: TokenService, clock: FakeClock) -> None:
    pair = await service.issue_pair("user-1")
    clock.advance(timedelta(days=31))
    with pytest.raises(UnauthorizedError):
        await service.rotate(pair.refresh_token)


async def test_revoke_kills_family(service: TokenService) -> None:
    pair = await service.issue_pair("user-1")
    await service.revoke(pair.refresh_token)
    with pytest.raises(UnauthorizedError):
        await service.rotate(pair.refresh_token)


def test_access_codec_roundtrip_and_tamper() -> None:
    codec = JwtAccessTokenCodec("s1", ttl=timedelta(minutes=15))
    token = codec.issue("user-9")
    assert codec.verify(token) == "user-9"

    other = JwtAccessTokenCodec("different-secret", ttl=timedelta(minutes=15))
    with pytest.raises(UnauthorizedError):
        other.verify(token)


def test_access_codec_expiry() -> None:
    codec = JwtAccessTokenCodec("s1", ttl=timedelta(seconds=-1))
    with pytest.raises(UnauthorizedError):
        codec.verify(codec.issue("user-9"))
