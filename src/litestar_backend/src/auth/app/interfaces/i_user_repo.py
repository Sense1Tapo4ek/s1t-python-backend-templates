from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared.domain.auth import Role

from ...domain import UserRecord


class IUserRepo(Protocol):
    async def register(self, *, email: str, password_hash: str, role: Role) -> UserRecord:
        """Create a user AND stage its `user_registered` outbox row atomically.

        One transaction: the user row and the integration-event row commit
        together, so a failed insert emits no event. `email` must already be
        normalized (domain `normalize_email`).

        Raises:
            EmailTakenError: an ACTIVE user with this email already exists.
            PortError: the storage backend is unreachable or rejected the write.
        """
        ...

    async def find_credentials_by_email(self, email: str) -> tuple[UserRecord, str] | None:
        """Return (record, password_hash) for the ACTIVE user with `email`.

        None when no active user matches. The hash never leaves the auth
        context -- only the login use case consumes it.

        Raises:
            PortError: storage failure.
        """
        ...

    async def is_active(self, user_id: UUID) -> bool:
        """True iff the user exists and is not soft-deleted.

        Consulted on refresh-token rotation so deactivation cuts the refresh
        path even while old tokens are still unexpired.

        Raises:
            PortError: storage failure.
        """
        ...

    async def list_page(self, after: tuple[datetime, UUID] | None, limit: int) -> list[UserRecord]:
        """Active users, newest-first keyset page (created_at DESC, id DESC).

        Raises:
            PortError: storage failure.
        """
        ...

    async def soft_delete(self, user_id: UUID) -> bool:
        """Deactivate a user (set deleted_at). False when already gone/unknown.

        Frees the email for re-registration (the unique index is partial on
        active rows) and makes `is_active` False.

        Raises:
            PortError: storage failure.
        """
        ...
