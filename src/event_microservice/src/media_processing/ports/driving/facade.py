from dataclasses import dataclass
from uuid import UUID

from ...app import CompleteJobUC, OnVideoUploadedUC
from ...domain import JobKind


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaProcessingFacade:
    _on_uploaded: OnVideoUploadedUC
    _complete_job: CompleteJobUC

    async def on_uploaded(self, video_id: UUID) -> None:
        await self._on_uploaded(video_id)

    async def complete_job(self, video_id: UUID, kind: JobKind) -> None:
        await self._complete_job(video_id, kind)
