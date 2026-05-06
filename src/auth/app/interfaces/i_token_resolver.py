from typing import Protocol

from shared.domain.auth import Principal


class ITokenResolver(Protocol):
    async def resolve(self, token: str) -> Principal | None: ...
