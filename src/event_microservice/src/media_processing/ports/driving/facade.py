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
        """Fan out the 3 processing jobs for a freshly uploaded video."""
        await self._on_uploaded(video_id)

    async def complete_job(self, video_id: UUID, kind: JobKind) -> None:
        """Mark one job done; on the final kind, log completion and clear the join."""
        await self._complete_job(video_id, kind)
