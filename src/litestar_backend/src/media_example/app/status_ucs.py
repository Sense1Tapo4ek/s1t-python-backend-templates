from dataclasses import dataclass
from uuid import UUID

from .errors import VideoNotFound
from .interfaces import IUoW, IVideoRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkProcessingUC:
    _repo: IVideoRepo
    _uow: IUoW

    async def __call__(self, video_id: UUID) -> None:
        video = await self._repo.get_by_id(video_id)
        if video is None:
            raise VideoNotFound(video_id)
        video.mark_processing()
        async with self._uow:
            await self._repo.save(video)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkDoneUC:
    _repo: IVideoRepo
    _uow: IUoW

    async def __call__(self, video_id: UUID) -> None:
        video = await self._repo.get_by_id(video_id)
        if video is None:
            raise VideoNotFound(video_id)
        video.mark_done()
        async with self._uow:
            await self._repo.save(video)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkFailedUC:
    _repo: IVideoRepo
    _uow: IUoW

    async def __call__(self, video_id: UUID) -> None:
        video = await self._repo.get_by_id(video_id)
        if video is None:
            raise VideoNotFound(video_id)
        video.mark_failed()
        async with self._uow:
            await self._repo.save(video)
