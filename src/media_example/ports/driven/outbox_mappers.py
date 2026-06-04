from uuid import uuid4

import msgspec

from ...domain import VideoUploaded
from .integration_events import VideoUploadedIntegration


def to_integration(event: VideoUploaded) -> VideoUploadedIntegration:
    return VideoUploadedIntegration(
        event_id=uuid4(),
        video_id=event.video_id,
        source_key=event.source_key,
        uploaded_at=event.uploaded_at,
    )


def encode_payload(integration: VideoUploadedIntegration) -> bytes:
    return msgspec.json.encode(integration)
