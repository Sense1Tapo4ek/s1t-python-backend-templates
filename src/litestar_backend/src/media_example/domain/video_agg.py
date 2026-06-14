from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from .errors import EmptySourceKey, InvalidTransition
from .events import VideoUploaded
from .video_status_vo import VideoStatus

_ALLOWED: dict[VideoStatus, set[VideoStatus]] = {
    VideoStatus.PENDING: {VideoStatus.PROCESSING, VideoStatus.FAILED},
    VideoStatus.PROCESSING: {VideoStatus.DONE, VideoStatus.FAILED},
    VideoStatus.DONE: set(),
    VideoStatus.FAILED: set(),
}


@dataclass(slots=True, kw_only=True)
class Video:
    id: UUID = field(default_factory=uuid4)
    source_key: str
    status: VideoStatus = VideoStatus.PENDING
    uploaded_at: datetime
    document: dict[str, Any] = field(default_factory=dict)
    _events: list[VideoUploaded] = field(default_factory=list, repr=False)

    @classmethod
    def upload(
        cls,
        *,
        source_key: str,
        uploaded_at: datetime | None = None,
        document: dict[str, Any] | None = None,
    ) -> "Video":
        if not source_key:
            raise EmptySourceKey()
        ts = uploaded_at or datetime.now().astimezone()
        video = cls(source_key=source_key, uploaded_at=ts, document=document or {})
        video._events.append(
            VideoUploaded(video_id=video.id, source_key=source_key, uploaded_at=ts)
        )
        return video

    @classmethod
    def reconstitute(
        cls,
        *,
        id: UUID,
        source_key: str,
        status: VideoStatus,
        uploaded_at: datetime,
        document: dict[str, Any] | None = None,
    ) -> "Video":
        return cls(
            id=id,
            source_key=source_key,
            status=status,
            uploaded_at=uploaded_at,
            document=document or {},
        )

    def _transition(self, to: VideoStatus) -> None:
        if to not in _ALLOWED[self.status]:
            raise InvalidTransition(self.status.value, to.value)
        self.status = to

    def mark_processing(self) -> None:
        self._transition(VideoStatus.PROCESSING)

    def mark_done(self) -> None:
        self._transition(VideoStatus.DONE)

    def mark_failed(self) -> None:
        self._transition(VideoStatus.FAILED)

    def collect_events(self) -> list[VideoUploaded]:
        events = self._events.copy()
        self._events.clear()
        return events
