from dataclasses import dataclass

from shared.domain.auth import Principal

from ..interfaces import ITokenResolver


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthenticateUc:
    _resolver: ITokenResolver

    async def __call__(self, token: str) -> Principal | None:
        return await self._resolver.resolve(token)
