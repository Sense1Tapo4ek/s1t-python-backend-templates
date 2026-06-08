from dataclasses import dataclass
from uuid import UUID

from ...app import (
    ListVideosQuery,
    MarkDoneUC,
    MarkFailedUC,
    MarkProcessingUC,
    UploadVideoCommand,
    UploadVideoUC,
)
from .video_dto import UploadVideoRequest, VideoModel, to_model


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaFacade:
    _upload: UploadVideoUC
    _recent: ListVideosQuery
    _mark_processing: MarkProcessingUC
    _mark_done: MarkDoneUC
    _mark_failed: MarkFailedUC

    async def upload(self, request: UploadVideoRequest) -> VideoModel:
        return to_model(await self._upload(UploadVideoCommand(source_key=request.source_key)))

    async def list_recent(self, limit: int) -> list[VideoModel]:
        return [to_model(v) for v in await self._recent(limit)]

    async def mark_processing(self, video_id: UUID) -> None:
        await self._mark_processing(video_id)

    async def mark_done(self, video_id: UUID) -> None:
        await self._mark_done(video_id)

    async def mark_failed(self, video_id: UUID) -> None:
        await self._mark_failed(video_id)
