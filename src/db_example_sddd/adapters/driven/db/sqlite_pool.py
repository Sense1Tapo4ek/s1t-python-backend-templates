import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite

from .connection import configure


@dataclass(slots=True)
class SqlitePool:
    _path: Path
    _size: int = 4
    _queue: asyncio.Queue[aiosqlite.Connection] | None = field(default=None)

    async def open(self) -> None:
        if self._queue is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        q: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
        for _ in range(self._size):
            conn = await aiosqlite.connect(self._path)
            await configure(conn)
            await q.put(conn)
        self._queue = q

    async def close(self) -> None:
        if self._queue is None:
            return
        while not self._queue.empty():
            conn = self._queue.get_nowait()
            await conn.close()
        self._queue = None

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[aiosqlite.Connection]:
        if self._queue is None:
            raise RuntimeError("SqlitePool is not open")
        conn = await self._queue.get()
        try:
            yield conn
        except Exception:
            # Never return a connection to the pool mid-transaction: the next
            # borrower would inherit the open transaction and could commit
            # orphaned writes. Roll back before recycling.
            await conn.rollback()
            raise
        finally:
            await self._queue.put(conn)
