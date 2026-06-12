from typing import Protocol
from uuid import UUID


class IFeedPublisher(Protocol):
    async def publish(self, video_id: UUID, status: str) -> None:
        """Broadcast a status change to the live browser feed.

        Fire-and-forget fan-out over an ephemeral channel: no durability, no
        replay; subscribers connected at publish time receive the event.
        Called only AFTER the status transition is committed.

        Raises:
            PortError: the channel plugin is not running or its queue
                rejected the message. Callers treat this as best-effort:
                log and continue -- the transition is already committed.
        """
        ...
