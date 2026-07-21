from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from ...domain import Cursor, LogEntryVO, MalformedLogLine


class ILogFileSource(Protocol):
    async def read_last_lines(self, limit: int) -> tuple[list[str], int, int]: ...
    async def read_lines_before(self, offset: int, limit: int) -> tuple[list[str], int]: ...
    async def current_inode(self) -> int: ...
    def iter_all_lines(self) -> AsyncIterator[str]: ...
    def iter_new_lines(self, poll_ms: int) -> AsyncIterator[str]: ...


@dataclass(slots=True, kw_only=True)
class FileLogReader:
    """Implements ILogReader and ILogFollower over an injected ILogFileSource."""

    _source: ILogFileSource

    async def read_tail(self, limit: int) -> tuple[list[LogEntryVO], Cursor]:
        lines, offset, inode = await self._source.read_last_lines(limit)
        entries = self._map(lines)
        return entries, Cursor(inode=inode, offset=offset)

    async def read_before(self, cursor: Cursor, limit: int) -> tuple[list[LogEntryVO], Cursor]:
        live_inode = await self._source.current_inode()
        if cursor.inode != live_inode:
            return [], cursor
        lines, offset = await self._source.read_lines_before(cursor.offset, limit)
        entries = self._map(lines)
        return entries, Cursor(inode=live_inode, offset=offset)

    async def stream_all(self) -> AsyncIterator[str]:
        async for line in self._source.iter_all_lines():
            yield line

    async def follow(self, poll_ms: int) -> AsyncIterator[LogEntryVO]:
        async for line in self._source.iter_new_lines(poll_ms):
            try:
                yield LogEntryVO.parse(line)
            except MalformedLogLine:
                continue

    @staticmethod
    def _map(lines: list[str]) -> list[LogEntryVO]:
        entries: list[LogEntryVO] = []
        for line in lines:
            try:
                entries.append(LogEntryVO.parse(line))
            except MalformedLogLine:
                continue
        return entries
