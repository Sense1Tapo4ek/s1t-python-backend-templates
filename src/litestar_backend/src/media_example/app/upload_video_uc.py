from dataclasses import dataclass, field
from typing import Any

from shared.app import IClock

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
        return video
