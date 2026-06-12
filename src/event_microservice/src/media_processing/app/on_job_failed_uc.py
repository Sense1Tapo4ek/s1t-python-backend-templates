from dataclasses import dataclass
from uuid import UUID

import structlog

from .interfaces import IEventPublisher, IJoinStore

_log = structlog.get_logger("media_processing.on_job_failed")


@dataclass(frozen=True, slots=True, kw_only=True)
class OnJobFailedUC:
    _store: IJoinStore
    _publisher: IEventPublisher

    async def __call__(self, video_id: UUID) -> None:
        _log.info("video processing failed", video_id=str(video_id))
        await self._publisher.publish_failed(video_id)
        await self._store.clear(video_id)
