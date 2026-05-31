from dataclasses import dataclass

from ...domain import Cursor, LogEntryEnt
from ..interfaces import ILogReader


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadOlderLogsUc:
    """Reads the page of entries before `cursor`.

    When the reader returns the unchanged cursor with no entries, the
    history has been truncated by rotation (cursor inode no longer the
    live file). The caller surfaces this sentinel to stop "load more".
    """

    _reader: ILogReader

    async def __call__(
        self, cursor: Cursor, limit: int
    ) -> tuple[list[LogEntryEnt], Cursor]:
        return await self._reader.read_before(cursor, limit)
