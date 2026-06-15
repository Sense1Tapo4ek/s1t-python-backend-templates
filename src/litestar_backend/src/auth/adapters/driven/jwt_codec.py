from dataclasses import dataclass
from typing import Any

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey


@dataclass(frozen=True, slots=True)
class JwtKey:
    key: OctKey | None


def build_jwt_key(secret: str | None) -> JwtKey:
    if not secret:
        return JwtKey(key=None)
    return JwtKey(key=OctKey.import_key(secret))


@dataclass(frozen=True, slots=True, kw_only=True)
class JwtCodec:
    _key: JwtKey

    def encode(self, header: dict[str, Any], claims: dict[str, Any]) -> str | None:
        if self._key.key is None:
            return None
        return jwt.encode(header, claims, self._key.key)

    def decode(self, token: str) -> dict[str, Any] | None:
        if self._key.key is None:
            return None
        try:
            decoded = jwt.decode(token, self._key.key, algorithms=["HS256"])
        except (JoseError, ValueError):
            return None
        return dict(decoded.claims)
