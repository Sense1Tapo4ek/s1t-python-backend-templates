from dataclasses import dataclass
from uuid import UUID

from ..domain import JobKind
from .interfaces import IJobQueue


@dataclass(frozen=True, slots=True, kw_only=True)
class OnVideoUploadedUC:
    _queue: IJobQueue

    async def __call__(self, video_id: UUID) -> None:
        for kind in JobKind:
            await self._queue.enqueue(video_id, kind)
