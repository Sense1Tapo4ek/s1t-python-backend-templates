from datetime import datetime
from typing import Annotated
from uuid import UUID

import msgspec
from litestar.dto import MsgspecDTO

from ...domain import Video


class UploadVideoRequest(msgspec.Struct, kw_only=True):
    source_key: Annotated[str, msgspec.Meta(min_length=1, examples=["s3://bucket/a.mp4"])]


class VideoModel(msgspec.Struct, kw_only=True):
    id: UUID
    source_key: str
    status: str
    uploaded_at: datetime


VideoReadDTO = MsgspecDTO[VideoModel]


def to_model(video: Video) -> VideoModel:
    return VideoModel(
        id=video.id,
        source_key=video.source_key,
        status=video.status.value,
        uploaded_at=video.uploaded_at,
    )
