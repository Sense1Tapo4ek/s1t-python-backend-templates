from dataclasses import dataclass

from shared.app import IClock

from ..domain import Video, VideoUploaded
from .interfaces import IOutboxRepo, IUoW, IVideoRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadVideoCommand:
    source_key: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadVideoUC:
    _repo: IVideoRepo
    _uow: IUoW
    _outbox: IOutboxRepo
    _clock: IClock

    async def __call__(self, command: UploadVideoCommand) -> Video:
        video = Video.upload(source_key=command.source_key, uploaded_at=self._clock.now())
        async with self._uow:
            await self._repo.save(video)
            for event in video.collect_events():
                if isinstance(event, VideoUploaded):
                    await self._outbox.add(event)
        return video
