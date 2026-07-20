from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared.domain.auth import Role
from shared.generics.errors import DomainError


@dataclass(frozen=True, slots=True, kw_only=True)
class UserRecord:
    id: UUID
    email: str
    role: Role
    created_at: datetime


class EmailTakenError(DomainError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"email {email} is already registered")


def normalize_email(email: str) -> str:
    """Canonical form used for storage and lookup: trimmed, lowercased.

    Registration and login MUST both pass through this, or the active-email
    unique index and the login lookup would disagree on case variants.
    """
    return email.strip().lower()
