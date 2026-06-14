from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...app import (
    DeleteVideoUC,
    ListVideosQuery,
    MarkDoneUC,
    MarkFailedUC,
    MarkProcessingUC,
    UploadVideoCommand,
    UploadVideoUC,
)
from .video_cursor import encode_cursor
from .video_dto import UploadVideoRequest, VideoModel, VideoPage, to_model


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaFacade:
    """Public API of the media_example context for the HTTP actor.

    The single driving port; holds no logic -- each method maps one call to
    one use case and translates the domain result to a wire model.
    AppError/DomainError/PortError raised downstream propagate unchanged; the
    global exception handler maps them to HTTP status codes.
    """

    _upload: UploadVideoUC
    _recent: ListVideosQuery
    _mark_processing: MarkProcessingUC
    _mark_done: MarkDoneUC
    _mark_failed: MarkFailedUC
    _delete: DeleteVideoUC

    async def upload(self, request: UploadVideoRequest) -> VideoModel:
        """Register a newly uploaded video and stage its outbox event.

        Triggered by POST of a source key. Persists the video and a
        VideoUploaded outbox row in one transaction, then returns the
        created video as a wire model. Raises EmptySourceKey (domain) on a
        blank key, PortError on a storage failure.
        """
        return to_model(
            await self._upload(
                UploadVideoCommand(source_key=request.source_key, document=request.document)
            )
        )

    async def list_page(self, after: tuple[datetime, UUID] | None, limit: int) -> VideoPage:
        """Return one keyset page of videos as wire models, newest-first.

        Triggered by GET /videos. `after` is the decoded cursor (the controller
        owns decoding + the 400 on a malformed token). `next_cursor` is set only
        when a full `limit` page came back -- a short page is the last page.
        Read-only. Raises PortError on a storage failure.
        """
        videos = await self._recent(after, limit)
        next_cursor = (
            encode_cursor(videos[-1].uploaded_at, videos[-1].id) if len(videos) == limit else None
        )
        return VideoPage(items=[to_model(v) for v in videos], next_cursor=next_cursor)

    async def mark_processing(self, video_id: UUID) -> None:
        """Transition a video to PROCESSING and persist it.

        Triggered by a status callback. Raises VideoNotFound (app) when no
        such video exists, InvalidTransition (domain) when the current
        status forbids the move, PortError on a storage failure. The
        post-commit feed broadcast is best-effort: a publish failure is
        logged and does not fail this call.
        """
        await self._mark_processing(video_id)

    async def mark_done(self, video_id: UUID) -> None:
        """Transition a video to DONE and persist it.

        Triggered by a status callback. Raises VideoNotFound (app) when no
        such video exists, InvalidTransition (domain) when the current
        status forbids the move, PortError on a storage failure. The
        post-commit feed broadcast is best-effort: a publish failure is
        logged and does not fail this call.
        """
        await self._mark_done(video_id)

    async def mark_failed(self, video_id: UUID) -> None:
        """Transition a video to FAILED and persist it.

        Triggered by a status callback. Raises VideoNotFound (app) when no
        such video exists, InvalidTransition (domain) when the current
        status forbids the move, PortError on a storage failure. The
        post-commit feed broadcast is best-effort: a publish failure is
        logged and does not fail this call.
        """
        await self._mark_failed(video_id)

    async def delete(self, video_id: UUID) -> None:
        """Soft-delete a video by id.

        Triggered by DELETE /videos/{id}. The row stops appearing in reads but is
        retained (deleted_at set). Raises VideoNotFound (app) when no active video
        with that id exists; PortError on a storage failure.
        """
        await self._delete(video_id)
