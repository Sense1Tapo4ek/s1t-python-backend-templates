import pytest

from auth.config import AuthConfig
from auth.ports.driven.gateways import StaticTokenResolver
from shared.domain.auth import Role


def _config(token: str | None) -> AuthConfig:
    return AuthConfig(admin_token=token)  # type: ignore[arg-type]


class TestStaticTokenResolver:
    @pytest.mark.asyncio
    async def test_correct_token_returns_admin_principal(self) -> None:
        resolver = StaticTokenResolver(_config=_config("s3cret"))
        principal = await resolver.resolve("s3cret")

        assert principal is not None
        assert principal.role == Role.ADMIN
        assert principal.token_id
        assert principal.token_id != "s3cret"  # never the raw token

    @pytest.mark.asyncio
    async def test_wrong_token_returns_none(self) -> None:
        resolver = StaticTokenResolver(_config=_config("s3cret"))
        assert await resolver.resolve("wrong") is None

    @pytest.mark.asyncio
    async def test_unconfigured_token_returns_none(self) -> None:
        resolver = StaticTokenResolver(_config=_config(None))
        assert await resolver.resolve("anything") is None
        assert await resolver.resolve("") is None

    @pytest.mark.asyncio
    async def test_token_id_is_deterministic(self) -> None:
        """The same token always produces the same token_id (sha256 prefix)."""
        resolver = StaticTokenResolver(_config=_config("s3cret"))
        a = await resolver.resolve("s3cret")
        b = await resolver.resolve("s3cret")
        assert a is not None and b is not None
        assert a.token_id == b.token_id

    @pytest.mark.asyncio
    async def test_token_id_is_short_hex(self) -> None:
        """token_id is exactly 8 lowercase hex chars (sha256 prefix)."""
        resolver = StaticTokenResolver(_config=_config("s3cret"))
        principal = await resolver.resolve("s3cret")
        assert principal is not None
        assert len(principal.token_id) == 8
        assert all(c in "0123456789abcdef" for c in principal.token_id)
