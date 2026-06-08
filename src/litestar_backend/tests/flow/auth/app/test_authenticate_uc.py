from unittest.mock import AsyncMock

import pytest

from auth.app import AuthenticateUc
from shared.domain.auth import Principal, Role


class TestAuthenticateUc:
    @pytest.mark.asyncio
    async def test_resolver_returns_principal_passed_through(self) -> None:
        principal = Principal(role=Role.ADMIN, token_id="abc12345")
        resolver = AsyncMock()
        resolver.resolve = AsyncMock(return_value=principal)
        uc = AuthenticateUc(_resolver=resolver)

        result = await uc("any-token")

        assert result is principal
        resolver.resolve.assert_awaited_once_with("any-token")

    @pytest.mark.asyncio
    async def test_resolver_returns_none_passed_through(self) -> None:
        resolver = AsyncMock()
        resolver.resolve = AsyncMock(return_value=None)
        uc = AuthenticateUc(_resolver=resolver)

        result = await uc("bogus")

        assert result is None
        resolver.resolve.assert_awaited_once_with("bogus")
