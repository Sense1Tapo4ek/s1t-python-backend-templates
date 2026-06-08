from typing import Protocol
from uuid import UUID

from ..domain import JobKind


class IJobQueue(Protocol):
    async def enqueue(self, video_id: UUID, kind: JobKind) -> None: ...


class IJoinStore(Protocol):
    async def add(self, video_id: UUID, kind: JobKind) -> int: ...
    async def clear(self, video_id: UUID) -> None: ...
