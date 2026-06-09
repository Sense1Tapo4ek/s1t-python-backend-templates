from collections.abc import AsyncIterator
from typing import Protocol

from ...domain import Cursor, LogEntryEnt


class ILogReader(Protocol):
    """Historical, paginated read-side of the JSONL log file.

    The concrete implementation (FileLogReader over a filesystem source)
    maps raw lines to LogEntryEnt and owns Cursor semantics. A Cursor is a
    (inode, byte-offset) pair: the inode pins the page to a specific file
    incarnation so a rotation invalidates stale cursors, and the offset is
    the byte position of the first entry of the page within that file.
    """

    async def read_tail(
        self,
        limit: int,
    ) -> tuple[list[LogEntryEnt], Cursor]:
        """Return the last `limit` entries, oldest-first, plus a back-cursor.

        Entries are ordered chronologically (oldest -> newest). The returned
        Cursor points at the oldest entry of this page and is the argument to
        pass to read_before to page further back. Malformed lines are skipped
        (and silently dropped), so the page MAY hold fewer than `limit`
        entries even when more lines exist. On an empty file the entry list
        is empty and the cursor has offset 0. Raises LogReadError if the file
        cannot be read.
        """
        ...

    async def read_before(
        self,
        cursor: Cursor,
        limit: int,
    ) -> tuple[list[LogEntryEnt], Cursor]:
        """Return up to `limit` entries ending just before `cursor`.

        Reads the slice strictly preceding the cursor offset, oldest-first,
        and returns the cursor of the oldest entry of the new page for
        continued backward paging. Reaching the start of the file yields a
        cursor with offset 0; a subsequent call then returns no entries.

        Rotation sentinel: if the cursor's inode no longer matches the live
        file (the history it referenced was rotated away), returns an empty
        list together with the UNCHANGED input cursor. Callers treat this as
        "no older history" and stop paging. Raises LogReadError if the file
        cannot be read.
        """
        ...

    def stream_all(self) -> AsyncIterator[str]:
        """Yield every raw JSONL line of a point-in-time snapshot, oldest-first.

        Opens the file once and streams the held descriptor to EOF with no
        re-stat or reopen, so concurrent appends and rotation after the open
        are not observed. Lines are emitted verbatim (newline-stripped, not
        parsed); a trailing partial line without a newline is discarded.
        Memory is O(1) regardless of file size. Raises LogReadError if the
        file cannot be opened.
        """
        ...
