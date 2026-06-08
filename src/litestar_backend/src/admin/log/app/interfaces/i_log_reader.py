from collections.abc import AsyncIterator
from typing import Protocol

from ...domain import Cursor, LogEntryEnt


class ILogReader(Protocol):
    """Historical read-side of the log file.

    read_tail returns the last `limit` entries in chronological order plus
    the cursor of the oldest returned entry. read_before reads `limit`
    entries ending just before `cursor`. stream_all yields raw JSONL lines
    from a point-in-time snapshot of the file (oldest first), for export.
    """

    async def read_tail(
        self,
        limit: int,
    ) -> tuple[list[LogEntryEnt], Cursor]: ...

    async def read_before(
        self,
        cursor: Cursor,
        limit: int,
    ) -> tuple[list[LogEntryEnt], Cursor]: ...

    def stream_all(self) -> AsyncIterator[str]: ...
