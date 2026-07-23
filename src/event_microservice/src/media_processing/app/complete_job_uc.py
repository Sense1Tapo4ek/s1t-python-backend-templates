from dataclasses import dataclass
from uuid import UUID

from shared.logging import Layer, layer_logger

from ..domain import JobKind, JoinPolicy
from .interfaces import IEventPublisher, IJoinStore

_log = layer_logger(Layer.APP, "media_processing.complete_job")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompleteJobUC:
    _store: IJoinStore
    _fan_out: int
    _publisher: IEventPublisher

    async def __call__(self, video_id: UUID, kind: JobKind) -> None:
        done = await self._store.add(video_id, kind)
        if JoinPolicy.is_complete(done_count=done, fan_out=self._fan_out):
            _log.info("video processed", video_id=str(video_id), jobs_done=done)
            await self._publisher.publish_processed(video_id)
            await self._store.clear(video_id)
