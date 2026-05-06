from dataclasses import dataclass

from shared.domain.auth import Principal

from ....app import AuthenticateUc


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthFacade:
    _authenticate_uc: AuthenticateUc

    async def authenticate(self, token: str) -> Principal | None:
        return await self._authenticate_uc(token)
