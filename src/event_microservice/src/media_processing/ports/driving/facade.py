from dataclasses import dataclass
from uuid import UUID

from ...app import CompleteJobUC, OnJobFailedUC, OnVideoUploadedUC
from ...domain import JobKind


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaProcessingFacade:
    """Public API of the media_processing context for the internal worker actor.

    Maps one call to one use case and holds no logic. PortError from the driven
    side propagates to the calling adapter.
    """

    _on_uploaded: OnVideoUploadedUC
    _complete_job: CompleteJobUC
    _on_failed: OnJobFailedUC

    async def on_uploaded(self, video_id: UUID, event_id: UUID) -> None:
        """Fan out the three processing jobs for a freshly uploaded video.

        Idempotent by event_id: a redelivered upload whose event_id was already
        fully processed is a no-op. Propagates PortError if a backend is unreachable.
        """
        await self._on_uploaded(video_id, event_id)

    async def complete_job(self, video_id: UUID, kind: JobKind) -> None:
        """Record one finished job; clear the join once all three are done.

        Propagates PortError if the join-store backend is unreachable.
        """
        await self._complete_job(video_id, kind)

    async def on_job_failed(self, video_id: UUID) -> None:
        """Record a terminal job failure: publish video_processing_failed, clear the join.

        Called by the SAQ after_process hook on the final retry attempt. The
        failed event is best-effort (publish errors are logged and swallowed);
        PortError still propagates if the join-store cleanup fails.
        """
        await self._on_failed(video_id)
