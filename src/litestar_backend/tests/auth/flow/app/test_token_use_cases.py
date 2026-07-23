from datetime import UTC, datetime

import pytest

from auth.app import IssueTokensUC, JwtDisabledError, RefreshTokensUC, RevokeTokenUC
from auth.domain import TokenPair, TokenType, VerifiedToken
from shared.domain.auth import Role

_FAR = datetime(2030, 1, 1, tzinfo=UTC)


class _Users:
    def __init__(self, *, active: bool = True) -> None:
        self._active = active
        self.checked: list[object] = []

    async def is_active(self, user_id) -> bool:
        self.checked.append(user_id)
        return self._active


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

    def issue_pair(self, *, role: Role, subject: str | None = None) -> TokenPair | None:
        self.issue_calls.append(role)
        self.issue_subjects: list[str | None] = getattr(self, "issue_subjects", [])
        self.issue_subjects.append(subject)
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
    uc = RefreshTokensUC(_jwt=jwt, _denylist=denylist, _clock=_Clock(), _users=_Users())

    result = await uc("refresh-token")

    assert result is new_pair
    assert jwt.verify_types == [TokenType.REFRESH]
    assert [jti for jti, _ in denylist.added] == ["old"]


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token() -> None:
    """Given an unverifiable refresh token, When RefreshTokensUC runs, Then None and no rotation."""
    denylist = _Denylist()
    uc = RefreshTokensUC(
        _jwt=_Jwt(verified=None), _denylist=denylist, _clock=_Clock(), _users=_Users()
    )
    assert await uc("garbage") is None
    assert denylist.added == []


@pytest.mark.asyncio
async def test_refresh_rejects_already_denylisted() -> None:
    """Given a refresh token whose jti is already denylisted (reuse), When refreshing, Then None."""
    jwt = _Jwt(verified=VerifiedToken(role=Role.ADMIN, jti="reused", expires_at=_FAR))
    denylist = _Denylist(denied={"reused"})
    uc = RefreshTokensUC(_jwt=jwt, _denylist=denylist, _clock=_Clock(), _users=_Users())
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


@pytest.mark.asyncio
async def test_refresh_of_deactivated_user_is_rejected() -> None:
    """Given a refresh token whose subject is a deactivated user,
    When refreshing, Then None -- deactivation cuts the refresh path."""
    verified = VerifiedToken(
        role=Role.USER,
        jti="jti-user",
        expires_at=_FAR,
        subject="00000000-0000-0000-0000-000000000001",
    )
    jwt = _Jwt(pair=TokenPair(access="a", refresh="r", expires_in=900), verified=verified)
    users = _Users(active=False)
    uc = RefreshTokensUC(_jwt=jwt, _denylist=_Denylist(), _clock=_Clock(), _users=users)

    assert await uc("some-refresh") is None
    assert len(users.checked) == 1


@pytest.mark.asyncio
async def test_refresh_of_active_user_reissues_with_same_subject() -> None:
    """Given an active user's refresh token, When refreshing, Then the new
    pair keeps the subject."""
    subject = "00000000-0000-0000-0000-000000000002"
    verified = VerifiedToken(role=Role.USER, jti="jti-user2", expires_at=_FAR, subject=subject)
    jwt = _Jwt(pair=TokenPair(access="a", refresh="r", expires_in=900), verified=verified)
    uc = RefreshTokensUC(_jwt=jwt, _denylist=_Denylist(), _clock=_Clock(), _users=_Users())

    pair = await uc("some-refresh")

    assert pair is not None
    assert jwt.issue_subjects == [subject]


@pytest.mark.asyncio
async def test_refresh_role_only_token_skips_user_check() -> None:
    """Given an admin role-only refresh token (no subject), When refreshing,
    Then the user repo is never consulted."""
    verified = VerifiedToken(role=Role.ADMIN, jti="jti-admin", expires_at=_FAR)
    jwt = _Jwt(pair=TokenPair(access="a", refresh="r", expires_in=900), verified=verified)
    users = _Users()
    uc = RefreshTokensUC(_jwt=jwt, _denylist=_Denylist(), _clock=_Clock(), _users=users)

    assert await uc("some-refresh") is not None
    assert users.checked == []
