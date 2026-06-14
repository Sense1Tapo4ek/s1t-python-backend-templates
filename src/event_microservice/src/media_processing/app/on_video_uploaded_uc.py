from dataclasses import dataclass
from uuid import UUID

from ..domain import JobKind
from .interfaces import IEventPublisher, IInboxStore, IJobQueue


@dataclass(frozen=True, slots=True, kw_only=True)
class OnVideoUploadedUC:
    _queue: IJobQueue
    _publisher: IEventPublisher
    _inbox: IInboxStore

    async def __call__(self, video_id: UUID, event_id: UUID) -> None:
        if await self._inbox.seen(event_id):
            return
        for kind in JobKind:
            await self._queue.enqueue(video_id, kind)
        await self._publisher.publish_started(video_id)
        await self._inbox.mark_processed(event_id)
