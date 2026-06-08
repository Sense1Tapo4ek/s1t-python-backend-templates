from datetime import datetime
from uuid import UUID

import msgspec


class VideoUploadedSchema(msgspec.Struct, frozen=True, kw_only=True):
    event_id: UUID
    video_id: UUID
    source_key: str
    uploaded_at: datetime
    event_type: str = "video_uploaded"
    version: int = 1
