from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ..domain import Video
from .interfaces import IVideoRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ListVideosQuery:
    _repo: IVideoRepo

    async def __call__(self, after: tuple[datetime, UUID] | None, limit: int) -> list[Video]:
        return await self._repo.list_page(after, limit)
