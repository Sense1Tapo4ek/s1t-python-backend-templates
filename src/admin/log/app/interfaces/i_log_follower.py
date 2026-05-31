from collections.abc import AsyncIterator
from typing import Protocol

from ...domain import LogEntryEnt


class ILogFollower(Protocol):
    """Live tail of the log file (tail -F semantics).

    follow yields entries appended after current EOF and survives
    rotation. Delivery across the rotation gap is best-effort
    (at-most-once).
    """

    def follow(self, poll_ms: int) -> AsyncIterator[LogEntryEnt]: ...
