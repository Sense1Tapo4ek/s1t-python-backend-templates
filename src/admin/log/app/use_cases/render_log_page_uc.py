from dataclasses import dataclass

import structlog

from ...app.interfaces import ILogReader
from ...domain import LogEntryEnt, LogFilterVo, LogId

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderLogPageUc:
    _reader: ILogReader
    _tail_size: int

    async def __call__(
        self,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]:
        entries, cursor, has_more = await self._reader.tail(
            self._tail_size,
            filter_vo,
        )
        _log.debug(
            "page rendered",
            tail_size=self._tail_size,
            returned=len(entries),
            cursor=cursor,
            has_more=has_more,
        )
        return entries, cursor, has_more
