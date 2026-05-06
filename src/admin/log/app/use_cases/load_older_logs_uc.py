from dataclasses import dataclass

import structlog

from ...app.interfaces import ILogReader
from ...domain import LogEntryEnt, LogFilterVo, LogId

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadOlderLogsUc:
    _reader: ILogReader
    _chunk_size: int

    async def __call__(
        self,
        cursor: LogId,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]:
        entries, next_cursor, has_more = await self._reader.read_before(
            cursor,
            self._chunk_size,
            filter_vo,
        )
        _log.debug(
            "older loaded",
            cursor_in=cursor,
            returned=len(entries),
            cursor_out=next_cursor,
            has_more=has_more,
        )
        return entries, next_cursor, has_more
