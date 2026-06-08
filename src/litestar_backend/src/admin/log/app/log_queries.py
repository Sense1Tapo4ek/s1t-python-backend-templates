from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..domain import Cursor, LogEntryEnt
from .interfaces import ILogFollower, ILogReader


@dataclass(frozen=True, slots=True, kw_only=True)
class LogQueries:
    _reader: ILogReader
    _follower: ILogFollower

    async def render_page(self, limit: int) -> tuple[list[LogEntryEnt], Cursor]:
        return await self._reader.read_tail(limit)

    async def load_older(
        self, cursor: Cursor, limit: int
    ) -> tuple[list[LogEntryEnt], Cursor]:
        # Reader returning the unchanged cursor with no entries is the
        # rotation sentinel (history truncated); the caller surfaces it to
        # stop "load more".
        return await self._reader.read_before(cursor, limit)

    async def stream_tail(self, poll_ms: int) -> AsyncIterator[LogEntryEnt]:
        async for entry in self._follower.follow(poll_ms):
            yield entry
