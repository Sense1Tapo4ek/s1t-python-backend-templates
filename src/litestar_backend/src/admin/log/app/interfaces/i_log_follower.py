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
        the async iterator.

        Survives rotation: on an inode change or size shrink it reopens at the
        new file's start. In truncate-mode rotation (the path keeps its inode)
        the old tail is drained best-effort first; in rename-mode (the
        logrotate default) the path already resolves to the new inode, so the
        old tail between the last poll and the rename is lost. Delivery across
        any rotation gap is therefore at-most-once. Malformed
        lines are skipped, not yielded. Transient stat/read errors during the
        poll loop are tolerated and retried on the next tick; they do not
        terminate the stream.
        """
        ...
