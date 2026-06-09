from dataclasses import dataclass
from uuid import UUID

from ...app import CompleteJobUC, OnVideoUploadedUC
from ...domain import JobKind


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaProcessingFacade:
    """Public API of the media_processing context for the internal worker actor.

    Maps one call to one use case and holds no logic. PortError from the driven
    side propagates to the calling adapter.
    """

    _on_uploaded: OnVideoUploadedUC
    _complete_job: CompleteJobUC

    async def on_uploaded(self, video_id: UUID) -> None:
        """Fan out the three processing jobs for a freshly uploaded video.

        Propagates PortError if the job-queue backend is unreachable.
        """
        await self._on_uploaded(video_id)

    async def complete_job(self, video_id: UUID, kind: JobKind) -> None:
        """Record one finished job; clear the join once all three are done.

        Propagates PortError if the join-store backend is unreachable.
        """
        await self._complete_job(video_id, kind)
