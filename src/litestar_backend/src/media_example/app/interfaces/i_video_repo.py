from datetime import datetime
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

    async def list_page(self, after: tuple[datetime, UUID] | None, limit: int) -> list[Video]:
        """Return up to `limit` videos newest-first by (uploaded_at, id) DESC.

        Keyset pagination: when `after` is the (uploaded_at, id) of the last row
        of the previous page, only strictly-older rows are returned, so paging
        never skips or repeats a row even when timestamps tie. `after=None`
        yields the first page. Read-only. Raises PortError on a storage failure.
        """
        ...
