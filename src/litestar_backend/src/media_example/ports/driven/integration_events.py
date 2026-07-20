from datetime import datetime
from uuid import UUID

from shared.generics.integration_event import IntegrationEvent

VIDEO_UPLOADED_STREAM = "video_uploaded"


class VideoUploadedIntegration(IntegrationEvent, frozen=True, kw_only=True):
    event_type: str = "video_uploaded"
    video_id: UUID
    source_key: str
    uploaded_at: datetime
