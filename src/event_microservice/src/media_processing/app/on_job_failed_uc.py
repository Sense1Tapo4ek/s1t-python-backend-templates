from dataclasses import dataclass
from uuid import UUID

from shared.generics.errors import PortError
from shared.logging import Layer, layer_logger

from .interfaces import IEventPublisher, IJoinStore

_log = layer_logger(Layer.APP, "media_processing.on_job_failed")


@dataclass(frozen=True, slots=True, kw_only=True)
class OnJobFailedUC:
    _store: IJoinStore
    _publisher: IEventPublisher

    async def __call__(self, video_id: UUID) -> None:
        _log.info("video processing failed", video_id=str(video_id))
        # AT-MOST-ONCE: a lost failed-event is cheaper than blocking cleanup;
        # the backend's join TTL bounds any orphan this would otherwise leave.
        try:
            await self._publisher.publish_failed(video_id)
        except PortError:
            _log.exception("video_processing_failed publish failed", video_id=str(video_id))
        await self._store.clear(video_id)
