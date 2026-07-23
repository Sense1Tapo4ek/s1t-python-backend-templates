from dataclasses import dataclass, field
from typing import Any

from shared.app import IClock
from shared.logging import Layer, layer_logger

from ..domain import Video
from .interfaces import IOutboxRepo, IUoW, IVideoRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadVideoCommand:
    source_key: str
    document: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadVideoUC:
    _repo: IVideoRepo
    _uow: IUoW
    _outbox: IOutboxRepo
    _clock: IClock

    async def __call__(self, command: UploadVideoCommand) -> Video:
        video = Video.upload(
            source_key=command.source_key,
            uploaded_at=self._clock.now(),
            document=command.document,
        )
        async with self._uow:
            await self._repo.save(video)
            for event in video.collect_events():
                await self._outbox.add(event)
        # Backend edge of the cross-service correlation chain: video_id logged
        # here lets a grep across both services follow the whole causal chain;
        # trace_id (merged via contextvar) pins it to the originating request.
        # Built at the call site (S-DDD logging rule 3: bind layer at the
        # operation boundary), not as a module global -- see structlog.md.
        layer_logger(Layer.APP, "UploadVideoUC").info("video registered", video_id=str(video.id))
        return video
