from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

import msgspec
from litestar.dto import MsgspecDTO

from ...domain import Video


class UploadVideoRequest(msgspec.Struct, kw_only=True):
    source_key: Annotated[
        str,
        msgspec.Meta(
            min_length=1,
            description="Storage key of the uploaded source video.",
            examples=["s3://bucket/a.mp4"],
        ),
    ]
    document: dict[str, Any] = msgspec.field(default_factory=dict)


class VideoModel(msgspec.Struct, kw_only=True):
    id: UUID
    source_key: Annotated[
        str,
        msgspec.Meta(
            description="Storage key of the source video.",
            examples=["s3://bucket/a.mp4"],
        ),
    ]
    status: Annotated[
        str,
        msgspec.Meta(
            description="Processing status: pending, processing, done or failed.",
            examples=["pending"],
        ),
    ]
    uploaded_at: datetime
    document: dict[str, Any] = msgspec.field(default_factory=dict)


VideoReadDTO = MsgspecDTO[VideoModel]


def to_model(video: Video) -> VideoModel:
    return VideoModel(
        id=video.id,
        source_key=video.source_key,
        status=video.status.value,
        uploaded_at=video.uploaded_at,
        document=video.document,
    )
