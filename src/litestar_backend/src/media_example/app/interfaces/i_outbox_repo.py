from typing import Protocol

from ...domain import VideoUploaded


class IOutboxRepo(Protocol):
    async def add(self, event: VideoUploaded) -> None:
        """Stage `event` as one outbox row in the caller's transaction.

        Does NOT commit -- the outbox row and the video row commit atomically
        through the same IUoW, so a failed transaction emits no event. The
        relay worker drains committed rows to the Valkey stream out of band.
        Raises PortError on a storage failure.
        """
        ...
