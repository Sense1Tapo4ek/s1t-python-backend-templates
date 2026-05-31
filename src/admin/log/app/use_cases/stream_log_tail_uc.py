from collections.abc import AsyncIterator
from dataclasses import dataclass

from ...domain import LogEntryEnt
from ..interfaces import ILogFollower


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamLogTailUc:
    """Yields log entries forever as they are appended to the file.

    No server-side filtering: level/substring filtering is the client's
    job over already-loaded rows.
    """

    _follower: ILogFollower

    async def __call__(self, poll_ms: int) -> AsyncIterator[LogEntryEnt]:
        async for entry in self._follower.follow(poll_ms):
            yield entry
