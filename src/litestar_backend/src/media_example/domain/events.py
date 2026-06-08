from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoUploaded:
    video_id: UUID
    source_key: str
    uploaded_at: datetime
