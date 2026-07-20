from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from shared.app import IClock
from shared.domain.auth import Role

from ...app import IJwtCodec
from ...domain import TokenPair, TokenType, VerifiedToken

_HEADER = {"alg": "HS256", "typ": "JWT"}


@dataclass(frozen=True, slots=True, kw_only=True)
class JwtService:
    _codec: IJwtCodec
    _clock: IClock
    _issuer: str
    _access_ttl: int
    _refresh_ttl: int

    def issue_pair(self, *, role: Role, subject: str | None = None) -> TokenPair | None:
        now = self._clock.now()
        access = self._codec.encode(
            _HEADER, self._claims(role, TokenType.ACCESS, self._access_ttl, now, subject)
        )
        if access is None:
            return None  # JWT disabled
        refresh = self._codec.encode(
            _HEADER, self._claims(role, TokenType.REFRESH, self._refresh_ttl, now, subject)
        )
        if refresh is None:
            return None
        return TokenPair(access=access, refresh=refresh, expires_in=self._access_ttl)

    def verify(self, token: str, *, expected_type: TokenType | None = None) -> VerifiedToken | None:
        claims = self._codec.decode(token)
        if claims is None:
            return None
        if claims.get("iss") != self._issuer:
            return None
        if expected_type is not None and claims.get("type") != expected_type.value:
            return None
        role_value = claims.get("role")
        jti = claims.get("jti")
        exp = claims.get("exp")
        if not isinstance(role_value, str) or not isinstance(jti, str) or not isinstance(exp, int):
            return None
        try:
            role = Role(role_value)
        except ValueError:
            return None
        expires_at = datetime.fromtimestamp(exp, tz=UTC)
        if expires_at <= self._clock.now():
            return None
        sub = claims.get("sub")
        # A role-only pair carries sub == role.value; expose subject only when
        # it actually identifies a stored user.
        subject = sub if isinstance(sub, str) and sub != role.value else None
        return VerifiedToken(role=role, jti=jti, expires_at=expires_at, subject=subject)

    def _claims(
        self, role: Role, token_type: TokenType, ttl: int, now: datetime, subject: str | None
    ) -> dict[str, object]:
        return {
            "iss": self._issuer,
            "sub": subject if subject is not None else role.value,
            "role": role.value,
            "type": token_type.value,
            "jti": uuid4().hex,
            "iat": now,
            "exp": now + timedelta(seconds=ttl),
        }
