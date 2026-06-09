from typing import Protocol

from ...domain import VideoUploaded


class IOutboxRepo(Protocol):
    async def add(self, event: VideoUploaded) -> None:
        """Stage a VideoUploaded as one transactional-outbox row.

        Maps the domain event to its integration schema, assigns a fresh
        event_id, encodes the payload, and inserts one outbox row. Writes
        within the caller's session but does NOT commit -- the outbox row
        and the video row commit atomically through the same IUoW, so a
        failed transaction emits no event. The relay worker drains
        committed rows to the Valkey stream out of band. Raises PortError
        on a storage failure.
        """
        ...
