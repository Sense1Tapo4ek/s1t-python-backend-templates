from datetime import UTC, datetime

import pytest

from auth.domain import VerifiedToken
from auth.ports.driven import CompositeTokenResolver, JwtTokenResolver
from shared.domain.auth import Principal, Role


class _FakeVerifier:
    def __init__(self, result: VerifiedToken | None) -> None:
        self._result = result

    def verify(self, token, *, expected_type=None):
        return self._result


class _FakeDenylist:
    def __init__(self, *, denied: set[str] | None = None) -> None:
        self._denied = denied or set()

    async def add(self, jti, *, ttl_seconds) -> None:  # pragma: no cover - unused here
        self._denied.add(jti)

    async def contains(self, jti) -> bool:
        return jti in self._denied


class _StubResolver:
    def __init__(self, principal: Principal | None) -> None:
        self._principal = principal

    async def resolve(self, token: str) -> Principal | None:
        return self._principal


def _verified() -> VerifiedToken:
    return VerifiedToken(role=Role.ADMIN, jti="jti-1", expires_at=datetime(2030, 1, 1, tzinfo=UTC))


@pytest.mark.asyncio
async def test_non_jwt_shape_is_skipped() -> None:
    """Given an opaque (dot-less) token, When resolving, Then verifier is never consulted -> None."""
    resolver = JwtTokenResolver(_verifier=_FakeVerifier(_verified()), _denylist=_FakeDenylist())
    assert await resolver.resolve("opaque-admin-token") is None


@pytest.mark.asyncio
async def test_valid_access_token_resolves_to_principal() -> None:
    """Given a verifiable, non-denylisted JWT, When resolving, Then ADMIN principal with jti token_id."""
    resolver = JwtTokenResolver(_verifier=_FakeVerifier(_verified()), _denylist=_FakeDenylist())
    principal = await resolver.resolve("a.b.c")
    assert principal == Principal(role=Role.ADMIN, token_id="jti-1")


@pytest.mark.asyncio
async def test_denylisted_jti_is_rejected() -> None:
    """Given a verifiable JWT whose jti is denylisted, When resolving, Then None."""
    resolver = JwtTokenResolver(
        _verifier=_FakeVerifier(_verified()),
        _denylist=_FakeDenylist(denied={"jti-1"}),
    )
    assert await resolver.resolve("a.b.c") is None


@pytest.mark.asyncio
async def test_composite_returns_first_non_none() -> None:
    """Given two resolvers, When the first yields None, Then the second's principal is used."""
    admin = Principal(role=Role.ADMIN, token_id="static")
    composite = CompositeTokenResolver(_resolvers=(_StubResolver(None), _StubResolver(admin)))
    assert await composite.resolve("whatever") == admin


@pytest.mark.asyncio
async def test_composite_returns_none_when_all_miss() -> None:
    """Given resolvers that all miss, When resolving, Then None."""
    composite = CompositeTokenResolver(_resolvers=(_StubResolver(None), _StubResolver(None)))
    assert await composite.resolve("whatever") is None
