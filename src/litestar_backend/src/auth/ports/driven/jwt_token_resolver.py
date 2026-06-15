from dataclasses import dataclass

from shared.domain.auth import Principal

from ...app import IDenylist, IJwtService
from ...domain import TokenType


@dataclass(frozen=True, slots=True, kw_only=True)
class JwtTokenResolver:
    _jwt: IJwtService
    _denylist: IDenylist

    async def resolve(self, token: str) -> Principal | None:
        # Shape gate: a compact JWS has exactly two dots. Opaque credentials
        # (static admin token, future API keys) have none -- skip them cheaply
        # so non-JWT requests never touch the verifier or Valkey denylist.
        if token.count(".") != 2:
            return None
        verified = self._jwt.verify(token, expected_type=TokenType.ACCESS)
        if verified is None:
            return None
        if await self._denylist.contains(verified.jti):
            return None
        return Principal(role=verified.role, token_id=verified.jti)
