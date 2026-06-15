from datetime import UTC, datetime

import pytest

from auth.app import IssueTokensUC, JwtDisabledError, RefreshTokensUC, RevokeTokenUC
from auth.domain import TokenPair, TokenType, VerifiedToken
from shared.domain.auth import Role

_FAR = datetime(2030, 1, 1, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)


class _Jwt:
    def __init__(
        self, *, pair: TokenPair | None = None, verified: VerifiedToken | None = None
    ) -> None:
        self._pair = pair
        self._verified = verified
        self.issue_calls: list[Role] = []
        self.verify_types: list[TokenType | None] = []

    def issue_pair(self, *, role: Role) -> TokenPair | None:
        self.issue_calls.append(role)
        return self._pair

    def verify(self, token, *, expected_type=None):
        self.verify_types.append(expected_type)
        return self._verified


class _Denylist:
    def __init__(self, *, denied: set[str] | None = None) -> None:
        self.added: list[tuple[str, int]] = []
        self._denied = denied or set()

    async def add(self, jti, *, ttl_seconds) -> None:
        self.added.append((jti, ttl_seconds))
        self._denied.add(jti)

    async def contains(self, jti) -> bool:
        return jti in self._denied


def test_issue_returns_pair() -> None:
    """Given an enabled issuer, When IssueTokensUC runs, Then it returns the pair for the role."""
    pair = TokenPair(access="a", refresh="r", expires_in=900)
    jwt = _Jwt(pair=pair)
    uc = IssueTokensUC(_jwt=jwt)
    assert uc(role=Role.ADMIN) is pair
    assert jwt.issue_calls == [Role.ADMIN]


def test_issue_raises_when_disabled() -> None:
    """Given a disabled issuer (None), When IssueTokensUC runs, Then JwtDisabledError."""
    uc = IssueTokensUC(_jwt=_Jwt(pair=None))
    with pytest.raises(JwtDisabledError):
        uc(role=Role.ADMIN)


@pytest.mark.asyncio
async def test_refresh_rotates_and_revokes_old() -> None:
    """Given a valid refresh token, When RefreshTokensUC runs, Then old jti is denylisted and a new pair returned."""
    new_pair = TokenPair(access="a2", refresh="r2", expires_in=900)
    jwt = _Jwt(pair=new_pair, verified=VerifiedToken(role=Role.ADMIN, jti="old", expires_at=_FAR))
    denylist = _Denylist()
    uc = RefreshTokensUC(_jwt=jwt, _denylist=denylist, _clock=_Clock())

    result = await uc("refresh-token")

    assert result is new_pair
    assert jwt.verify_types == [TokenType.REFRESH]
    assert [jti for jti, _ in denylist.added] == ["old"]


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token() -> None:
    """Given an unverifiable refresh token, When RefreshTokensUC runs, Then None and no rotation."""
    denylist = _Denylist()
    uc = RefreshTokensUC(_jwt=_Jwt(verified=None), _denylist=denylist, _clock=_Clock())
    assert await uc("garbage") is None
    assert denylist.added == []


@pytest.mark.asyncio
async def test_refresh_rejects_already_denylisted() -> None:
    """Given a refresh token whose jti is already denylisted (reuse), When refreshing, Then None."""
    jwt = _Jwt(verified=VerifiedToken(role=Role.ADMIN, jti="reused", expires_at=_FAR))
    denylist = _Denylist(denied={"reused"})
    uc = RefreshTokensUC(_jwt=jwt, _denylist=denylist, _clock=_Clock())
    assert await uc("reused-refresh") is None


@pytest.mark.asyncio
async def test_revoke_denylists_verified_jti() -> None:
    """Given a valid token, When RevokeTokenUC runs, Then its jti is denylisted with a positive ttl."""
    jwt = _Jwt(verified=VerifiedToken(role=Role.ADMIN, jti="live", expires_at=_FAR))
    denylist = _Denylist()
    uc = RevokeTokenUC(_jwt=jwt, _denylist=denylist, _clock=_Clock())
    await uc("some-token")
    assert len(denylist.added) == 1
    jti, ttl = denylist.added[0]
    assert jti == "live" and ttl > 0


@pytest.mark.asyncio
async def test_revoke_is_noop_for_invalid_token() -> None:
    """Given an unverifiable token, When RevokeTokenUC runs, Then nothing is denylisted (idempotent)."""
    denylist = _Denylist()
    uc = RevokeTokenUC(_jwt=_Jwt(verified=None), _denylist=denylist, _clock=_Clock())
    await uc("garbage")
    assert denylist.added == []
