from dataclasses import dataclass

from ...domain import Cursor, LogEntryEnt
from ..interfaces import ILogReader


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderLogPageUc:
    _reader: ILogReader

    async def __call__(self, limit: int) -> tuple[list[LogEntryEnt], Cursor]:
        return await self._reader.read_tail(limit)
