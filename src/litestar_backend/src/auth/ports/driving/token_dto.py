from typing import Annotated

import msgspec

from ...domain import TokenPair


class TokenPairResponse(msgspec.Struct, kw_only=True):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 0

    @classmethod
    def of(cls, pair: TokenPair) -> "TokenPairResponse":
        return cls(
            access_token=pair.access,
            refresh_token=pair.refresh,
            expires_in=pair.expires_in,
        )


class RefreshRequest(msgspec.Struct, kw_only=True):
    refresh_token: Annotated[str, msgspec.Meta(min_length=1)]


class RevokeRequest(msgspec.Struct, kw_only=True):
    token: Annotated[str, msgspec.Meta(min_length=1)]
