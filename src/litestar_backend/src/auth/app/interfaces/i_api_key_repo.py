from typing import Protocol
from uuid import UUID

from shared.domain.auth import Role

from ...domain import ApiKeyRecord


class IApiKeyRepo(Protocol):
    async def find_active_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        """Return the active (not soft-deleted) key whose hash matches, or None.

        This is the resolver's hot path (one read per `ak_` request). Soft-deleted
        rows are invisible.

        Raises:
            PortError: the database is unreachable or the query failed.
        """
        ...

    async def create(self, *, key_hash: str, name: str, role: Role) -> UUID:
        """Insert a new active key, returning its generated id.

        Raises:
            PortError: the database rejected the write (e.g. duplicate active hash).
        """
        ...

    async def list_active(self) -> list[ApiKeyRecord]:
        """Return all active keys, newest first. Never includes the secret/hash."""
        ...

    async def soft_delete(self, api_key_id: UUID) -> bool:
        """Mark an active key revoked (set deleted_at). Returns False if no active
        row with that id exists (already revoked or unknown)."""
        ...
