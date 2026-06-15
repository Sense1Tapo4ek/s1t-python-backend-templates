import math
from dataclasses import dataclass

from shared.app import IClock

from ..domain import TokenPair, TokenType
from .i_denylist import IDenylist
from .i_jwt_issuer import IJwtIssuer
from .i_jwt_verifier import IJwtVerifier


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshTokensUC:
    _verifier: IJwtVerifier
    _issuer: IJwtIssuer
    _denylist: IDenylist
    _clock: IClock

    async def __call__(self, refresh_token: str) -> TokenPair | None:
        verified = self._verifier.verify(refresh_token, expected_type=TokenType.REFRESH)
        if verified is None:
            return None
        if await self._denylist.contains(verified.jti):
            return None  # reuse of an already-rotated refresh token
        # ceil, not int: a token with <1s of life left still verifies (verify
        # rejects only expires_at <= now), so truncating to 0 would skip the
        # denylist write and leave it briefly un-revoked.
        ttl = math.ceil((verified.expires_at - self._clock.now()).total_seconds())
        await self._denylist.add(verified.jti, ttl_seconds=ttl)  # one-time use
        return self._issuer.issue_pair(role=verified.role)
