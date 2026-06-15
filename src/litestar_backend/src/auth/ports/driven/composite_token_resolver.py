from dataclasses import dataclass

from shared.domain.auth import Principal

from ...app import ITokenResolver


@dataclass(frozen=True, slots=True, kw_only=True)
class CompositeTokenResolver:
    _resolvers: tuple[ITokenResolver, ...]

    async def resolve(self, token: str) -> Principal | None:
        for resolver in self._resolvers:
            principal = await resolver.resolve(token)
            if principal is not None:
                return principal
        return None
