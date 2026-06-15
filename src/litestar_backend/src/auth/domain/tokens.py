from dataclasses import dataclass
from datetime import datetime

from shared.domain.auth import Role


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenPair:
    access: str
    refresh: str
    expires_in: int  # access-token lifetime in seconds


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifiedToken:
    role: Role
    jti: str
    expires_at: datetime
