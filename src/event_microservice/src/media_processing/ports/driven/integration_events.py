from datetime import datetime
from uuid import UUID

import msgspec


class VideoStatusIntegration(msgspec.Struct, frozen=True, kw_only=True):
    event_id: UUID
    event_type: str
    video_id: UUID
    occurred_at: datetime
    version: int = 1
