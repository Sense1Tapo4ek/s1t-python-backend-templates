from typing import Protocol
from uuid import UUID

from ...domain import Video


class IVideoRepo(Protocol):
    async def save(self, video: Video) -> None: ...
    async def get_by_id(self, video_id: UUID) -> Video | None: ...
    async def list_recent(self, limit: int) -> list[Video]: ...
