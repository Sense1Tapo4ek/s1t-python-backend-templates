from datetime import UTC, datetime

from auth.domain import TokenPair, TokenType, VerifiedToken
from shared.domain.auth import Role


def test_token_type_values() -> None:
    assert TokenType.ACCESS.value == "access"
    assert TokenType.REFRESH.value == "refresh"


def test_token_pair_is_frozen() -> None:
    pair = TokenPair(access="a", refresh="r", expires_in=900)
    assert pair.expires_in == 900
    try:
        pair.access = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("TokenPair must be frozen")


def test_verified_token_carries_role_jti_expiry() -> None:
    exp = datetime(2026, 1, 1, tzinfo=UTC)
    vt = VerifiedToken(role=Role.ADMIN, jti="abc", expires_at=exp)
    assert (vt.role, vt.jti, vt.expires_at) == (Role.ADMIN, "abc", exp)
