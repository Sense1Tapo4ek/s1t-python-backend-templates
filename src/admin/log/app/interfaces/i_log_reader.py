from collections.abc import AsyncGenerator
from typing import Protocol

from ...domain import LogEntryEnt, LogFilterVo, LogId


class ILogReader(Protocol):
    """Read-side contract for the log store.

    Implementations must:
    - return entries in chronological (ascending) order;
    - return cursor = id of the OLDEST entry in the page, suitable for
      passing back as `before` to fetch the previous page;
    - report `has_more=True` iff at least one row exists beyond the
      returned page (canonically via the `LIMIT size + 1` trick).

    `stream_after` is unbounded — it backs the SSE tail.
    """

    async def tail(
        self,
        size: int,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]: ...

    async def read_before(
        self,
        cursor: LogId,
        size: int,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]: ...

    def stream_after(
        self,
        cursor: LogId | None = None,
        filter_vo: LogFilterVo | None = None,
    ) -> AsyncGenerator[LogEntryEnt, None]: ...

    def stream_query(
        self,
        filter_vo: LogFilterVo | None = None,
    ) -> AsyncGenerator[LogEntryEnt, None]: ...
