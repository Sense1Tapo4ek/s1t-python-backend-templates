from dataclasses import dataclass
from uuid import UUID

from ..domain import JobKind
from .interfaces import IEventPublisher, IJobQueue


@dataclass(frozen=True, slots=True, kw_only=True)
class OnVideoUploadedUC:
    _queue: IJobQueue
    _publisher: IEventPublisher

    async def __call__(self, video_id: UUID) -> None:
        for kind in JobKind:
            await self._queue.enqueue(video_id, kind)
        await self._publisher.publish_started(video_id)
