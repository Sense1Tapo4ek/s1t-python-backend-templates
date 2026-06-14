from dataclasses import dataclass
from uuid import UUID

from .errors import VideoNotFound
from .interfaces import IUoW, IVideoRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteVideoUC:
    _repo: IVideoRepo
    _uow: IUoW

    async def __call__(self, video_id: UUID) -> None:
        async with self._uow:
            if not await self._repo.soft_delete(video_id):
                raise VideoNotFound(video_id)
