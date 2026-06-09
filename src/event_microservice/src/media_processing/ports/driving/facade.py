from dataclasses import dataclass
from uuid import UUID

from ...app import CompleteJobUC, OnVideoUploadedUC
from ...domain import JobKind


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaProcessingFacade:
    """Public API of the media_processing context (single internal actor: the worker).

    Entry point for both driving adapters: the FastStream consumer calls
    `on_uploaded`; each SAQ job calls `complete_job`. Holds no logic -- it maps
    one call to one use case. PortErrors from the driven side propagate to the
    adapter (the consumer acks/redelivers; the SAQ job retries).
    """

    _on_uploaded: OnVideoUploadedUC
    _complete_job: CompleteJobUC

    async def on_uploaded(self, video_id: UUID) -> None:
        """Fan out the three processing jobs for a freshly uploaded video.

        Triggered by the FastStream consumer on a video_uploaded event.
        Propagates PortError if the job-queue backend is unreachable.
        """
        await self._on_uploaded(video_id)

    async def complete_job(self, video_id: UUID, kind: JobKind) -> None:
        """Record one finished job; clear the join once all three are done.

        Triggered by each SAQ worker job on completion. Propagates PortError
        if the join-store backend is unreachable.
        """
        await self._complete_job(video_id, kind)
