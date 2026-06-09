from collections.abc import AsyncIterator
from typing import Protocol

from ...domain import LogEntryEnt


class ILogFollower(Protocol):
    """Live tail of the JSONL log file (tail -F semantics)."""

    def follow(self, poll_ms: int) -> AsyncIterator[LogEntryEnt]:
        """Yield entries appended after the current EOF, oldest-first, forever.

        Starts at the current end of the file (existing history is NOT
        replayed) and polls every `poll_ms` milliseconds for new bytes,
        yielding each newly-completed line parsed into a LogEntryEnt. The
        generator never completes on its own; the caller stops it by closing
        the async iterator (e.g. when the SSE client disconnects).

        Survives rotation: on an inode change or size shrink it drains the
        remainder of the old file, then reopens the new file at its start.
        Delivery across the rotation gap is best-effort (at-most-once) -- a
        line written to the old inode between polls may be lost. Malformed
        lines are skipped, not yielded. Transient stat/read errors during the
        poll loop are tolerated and retried on the next tick; they do not
        terminate the stream.
        """
        ...
