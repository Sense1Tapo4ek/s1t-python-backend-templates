import math
from dataclasses import dataclass

from shared.app import IClock

from ..interfaces import IDenylist, IJwtService


@dataclass(frozen=True, slots=True, kw_only=True)
class RevokeTokenUC:
    _jwt: IJwtService
    _denylist: IDenylist
    _clock: IClock

    async def __call__(self, token: str) -> None:
        verified = self._jwt.verify(token)  # any type
        if verified is None:
            return  # idempotent no-op on garbage/expired input
        # ceil, not int: a token with <1s of life left still verifies, so
        # truncating to 0 would skip the denylist write (see RefreshTokensUC).
        ttl = math.ceil((verified.expires_at - self._clock.now()).total_seconds())
        await self._denylist.add(verified.jti, ttl_seconds=ttl)
