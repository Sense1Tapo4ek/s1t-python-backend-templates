from dataclasses import dataclass
from typing import Protocol

from ...domain import Video


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredUpload:
    """A committed upload recovered from its idempotency key."""

    fingerprint: str
    video: Video


class IIdempotencyStore(Protocol):
    async def claim(self, key: str, *, fingerprint: str, video: Video) -> bool:
        """Stage the claim of `key` for `video` in the caller's transaction.

        Returns True when this caller won the key and the write it guards must
        proceed, False when the key is already claimed and the caller must
        write nothing. Does NOT commit -- the claim, the video row and the
        outbox row commit atomically through the same IUoW, so a key is never
        visible without the effect it names.

        A concurrent claim of the same key blocks until the first transaction
        commits or rolls back; the loser then observes False (winner
        committed) or True (winner rolled back). Raises PortError on a storage
        failure.
        """
        ...

    async def find(self, key: str) -> StoredUpload | None:
        """Return the committed upload behind `key`, or None if unclaimed.

        Reads only committed rows: a claim still in flight in another
        transaction reads as None. Callers use this after losing a claim to
        replay the winner's result. Expired rows are indistinguishable from
        unclaimed ones once purged. Raises PortError on a storage failure.
        """
        ...
