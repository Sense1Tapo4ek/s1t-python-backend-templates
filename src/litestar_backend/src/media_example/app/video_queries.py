from dataclasses import dataclass

from ..domain import Video
from .interfaces import IVideoRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ListVideosQuery:
    _repo: IVideoRepo

    async def __call__(self, limit: int) -> list[Video]:
        return await self._repo.list_recent(limit)
