from typing import Protocol
from uuid import UUID


class IFeedPublisher(Protocol):
    async def publish(self, video_id: UUID, status: str) -> None:
        """Broadcast a status change to the live browser feed.

        Fire-and-forget fan-out over an ephemeral channel: no durability, no
        replay; subscribers connected at publish time receive the event.
        Called only AFTER the status transition is committed.

        Best-effort by contract: NEVER raises. At-most-once delivery --
        implementations catch and log their own infra failures, so a lost
        feed event costs only a live-browser update and never fails the
        caller.
        """
        ...
