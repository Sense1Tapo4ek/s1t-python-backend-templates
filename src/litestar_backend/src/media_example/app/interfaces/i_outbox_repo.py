from typing import Protocol

from ...domain import VideoUploaded


class IOutboxRepo(Protocol):
    async def add(self, event: VideoUploaded) -> None: ...
