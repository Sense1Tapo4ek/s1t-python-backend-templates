import math
from dataclasses import dataclass
from uuid import UUID

from shared.app import IClock

from ...domain import TokenPair, TokenType
from ..interfaces import IDenylist, IJwtService, IUserRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshTokensUC:
    _jwt: IJwtService
    _denylist: IDenylist
    _clock: IClock
    _users: IUserRepo

    async def __call__(self, refresh_token: str) -> TokenPair | None:
        verified = self._jwt.verify(refresh_token, expected_type=TokenType.REFRESH)
        if verified is None:
            return None
        if await self._denylist.contains(verified.jti):
            return None  # reuse of an already-rotated refresh token
        if verified.subject is not None:
            # User-bound pair: deactivation must cut the refresh path even
            # while the token itself is still unexpired.
            try:
                user_id = UUID(verified.subject)
            except ValueError:
                return None
            if not await self._users.is_active(user_id):
                return None
        # ceil, not int: a token with <1s of life left still verifies (verify
        # rejects only expires_at <= now), so truncating to 0 would skip the
        # denylist write and leave it briefly un-revoked.
        ttl = math.ceil((verified.expires_at - self._clock.now()).total_seconds())
        await self._denylist.add(verified.jti, ttl_seconds=ttl)  # one-time use
        return self._jwt.issue_pair(role=verified.role, subject=verified.subject)
