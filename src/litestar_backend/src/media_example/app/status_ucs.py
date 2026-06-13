from dataclasses import dataclass
from uuid import UUID

import structlog

from shared.generics.errors import PortError

from .errors import VideoNotFound
from .interfaces import IFeedPublisher, IUoW, IVideoRepo

_log = structlog.get_logger("media_example.status_ucs")


async def _publish_best_effort(feed: IFeedPublisher, video_id: UUID, status: str) -> None:
    # AT-MOST-ONCE: the transition is already committed; a lost feed event
    # only costs a live-browser update and must not fail the caller.
    try:
        await feed.publish(video_id, status)
    except PortError:
        _log.warning("feed publish failed", video_id=str(video_id), status=status)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkProcessingUC:
    _repo: IVideoRepo
    _uow: IUoW
    _feed: IFeedPublisher

    async def __call__(self, video_id: UUID) -> None:
        video = await self._repo.get_by_id(video_id)
        if video is None:
            raise VideoNotFound(video_id)
        video.mark_processing()
        async with self._uow:
            await self._repo.save(video)
        await _publish_best_effort(self._feed, video_id, video.status.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkDoneUC:
    _repo: IVideoRepo
    _uow: IUoW
    _feed: IFeedPublisher

    async def __call__(self, video_id: UUID) -> None:
        video = await self._repo.get_by_id(video_id)
        if video is None:
            raise VideoNotFound(video_id)
        video.mark_done()
        async with self._uow:
            await self._repo.save(video)
        await _publish_best_effort(self._feed, video_id, video.status.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkFailedUC:
    _repo: IVideoRepo
    _uow: IUoW
    _feed: IFeedPublisher

    async def __call__(self, video_id: UUID) -> None:
        video = await self._repo.get_by_id(video_id)
        if video is None:
            raise VideoNotFound(video_id)
        video.mark_failed()
        async with self._uow:
            await self._repo.save(video)
        await _publish_best_effort(self._feed, video_id, video.status.value)
