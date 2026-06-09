from typing import Protocol
from uuid import UUID

from ...domain import Video


class IVideoRepo(Protocol):
    async def save(self, video: Video) -> None:
        """Persist a Video as an upsert keyed on its id.

        Insert when the id is new, update when it already exists. Writes one
        row but does NOT commit -- the surrounding IUoW owns the transaction
        boundary. Raises PortError on any underlying storage failure.
        """
        ...

    async def get_by_id(self, video_id: UUID) -> Video | None:
        """Load a single Video by id, or None if no such row exists.

        Read-only; never mutates state. Raises PortError on a storage
        failure (a missing row is None, not an error).
        """
        ...

    async def list_recent(self, limit: int) -> list[Video]:
        """Return the most recent videos, newest first.

        Ordered by uploaded_at descending and capped at `limit` rows;
        an empty table yields an empty list. Read-only. Raises
        PortError on a storage failure.
        """
        ...
