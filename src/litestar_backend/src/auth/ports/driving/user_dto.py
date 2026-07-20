from datetime import datetime
from typing import Annotated
from uuid import UUID

import msgspec

from ...domain import UserRecord

# Boundary shape-check only: full RFC 5322 belongs to an email round-trip we
# don't do. One '@' with something on both sides and a dot in the host part.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

EmailField = Annotated[str, msgspec.Meta(max_length=254, pattern=_EMAIL_PATTERN)]
PasswordField = Annotated[str, msgspec.Meta(min_length=8, max_length=128)]


class RegisterRequest(msgspec.Struct, kw_only=True):
    email: EmailField
    password: PasswordField


class LoginRequest(msgspec.Struct, kw_only=True):
    email: EmailField
    password: PasswordField


class UserResponse(msgspec.Struct, kw_only=True):
    id: UUID
    email: str
    role: str
    created_at: datetime

    @classmethod
    def of(cls, user: UserRecord) -> "UserResponse":
        return cls(id=user.id, email=user.email, role=user.role.value, created_at=user.created_at)


class MeResponse(msgspec.Struct, kw_only=True):
    subject: str | None  # user id for user-bound tokens, None for role-only credentials
    role: str
