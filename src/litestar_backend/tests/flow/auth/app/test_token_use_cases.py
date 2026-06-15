from datetime import UTC, datetime

import pytest

from auth.app import IssueTokensUC, JwtDisabledError, RefreshTokensUC, RevokeTokenUC
from auth.domain import TokenPair, TokenType, VerifiedToken
from shared.domain.auth import Role

_FAR = datetime(2030, 1, 1, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)


class _Issuer:
    def __init__(self, pair: TokenPair | None) -> None:
        self._pair = pair
        self.calls: list[Role] = []

    def issue_pair(self, *, role: Role) -> TokenPair | None:
        self.calls.append(role)
        return self._pair


class _Verifier:
    def __init__(self, result: VerifiedToken | None) -> None:
        self._result = result
        self.types: list[TokenType | None] = []

    def verify(self, token, *, expected_type=None):
        self.types.append(expected_type)
        return self._result


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
    issuer = _Issuer(pair)
    uc = IssueTokensUC(_issuer=issuer)
    assert uc(role=Role.ADMIN) is pair
    assert issuer.calls == [Role.ADMIN]


def test_issue_raises_when_disabled() -> None:
    """Given a disabled issuer (None), When IssueTokensUC runs, Then JwtDisabledError."""
    uc = IssueTokensUC(_issuer=_Issuer(None))
    with pytest.raises(JwtDisabledError):
        uc(role=Role.ADMIN)


@pytest.mark.asyncio
async def test_refresh_rotates_and_revokes_old() -> None:
    """Given a valid refresh token, When RefreshTokensUC runs, Then old jti is denylisted and a new pair returned."""
    new_pair = TokenPair(access="a2", refresh="r2", expires_in=900)
    verifier = _Verifier(VerifiedToken(role=Role.ADMIN, jti="old", expires_at=_FAR))
    denylist = _Denylist()
    uc = RefreshTokensUC(
        _verifier=verifier, _issuer=_Issuer(new_pair), _denylist=denylist, _clock=_Clock()
    )

    result = await uc("refresh-token")

    assert result is new_pair
    assert verifier.types == [TokenType.REFRESH]
    assert [jti for jti, _ in denylist.added] == ["old"]


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token() -> None:
    """Given an unverifiable refresh token, When RefreshTokensUC runs, Then None and no rotation."""
    denylist = _Denylist()
    uc = RefreshTokensUC(
        _verifier=_Verifier(None), _issuer=_Issuer(None), _denylist=denylist, _clock=_Clock()
    )
    assert await uc("garbage") is None
    assert denylist.added == []


@pytest.mark.asyncio
async def test_refresh_rejects_already_denylisted() -> None:
    """Given a refresh token whose jti is already denylisted (reuse), When refreshing, Then None."""
    verifier = _Verifier(VerifiedToken(role=Role.ADMIN, jti="reused", expires_at=_FAR))
    denylist = _Denylist(denied={"reused"})
    uc = RefreshTokensUC(
        _verifier=verifier, _issuer=_Issuer(None), _denylist=denylist, _clock=_Clock()
    )
    assert await uc("reused-refresh") is None


@pytest.mark.asyncio
async def test_revoke_denylists_verified_jti() -> None:
    """Given a valid token, When RevokeTokenUC runs, Then its jti is denylisted with a positive ttl."""
    verifier = _Verifier(VerifiedToken(role=Role.ADMIN, jti="live", expires_at=_FAR))
    denylist = _Denylist()
    uc = RevokeTokenUC(_verifier=verifier, _denylist=denylist, _clock=_Clock())
    await uc("some-token")
    assert len(denylist.added) == 1
    jti, ttl = denylist.added[0]
    assert jti == "live" and ttl > 0


@pytest.mark.asyncio
async def test_revoke_is_noop_for_invalid_token() -> None:
    """Given an unverifiable token, When RevokeTokenUC runs, Then nothing is denylisted (idempotent)."""
    denylist = _Denylist()
    uc = RevokeTokenUC(_verifier=_Verifier(None), _denylist=denylist, _clock=_Clock())
    await uc("garbage")
    assert denylist.added == []
