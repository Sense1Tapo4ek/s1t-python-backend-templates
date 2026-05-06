import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite


@dataclass(slots=True, kw_only=True)
class SQLiteConnection:
    _db_path: Path
    _reader_count: int = 4
    _writer: aiosqlite.Connection | None = None
    _readers: asyncio.Queue[aiosqlite.Connection] | None = None
    _write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def open(self) -> None:
        if self._writer is not None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._writer = await aiosqlite.connect(self._db_path)
        await self._configure(self._writer, read_only=False)

        readers: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
        for _ in range(self._reader_count):
            r = await aiosqlite.connect(
                f"file:{self._db_path}?mode=ro",
                uri=True,
            )
            await self._configure(r, read_only=True)
            await readers.put(r)
        self._readers = readers

    async def close(self) -> None:
        if self._writer is None:
            return
        await self._writer.close()
        self._writer = None
        if self._readers is not None:
            while not self._readers.empty():
                r = self._readers.get_nowait()
                await r.close()
            self._readers = None

    @staticmethod
    async def _configure(conn: aiosqlite.Connection, *, read_only: bool) -> None:
        conn.row_factory = aiosqlite.Row
        if not read_only:
            await conn.execute("PRAGMA journal_mode = WAL")
            await conn.execute("PRAGMA synchronous = NORMAL")
        await conn.execute("PRAGMA busy_timeout = 5000")
        await conn.execute("PRAGMA cache_size = -32768")
        await conn.execute("PRAGMA temp_store = MEMORY")
        if not read_only:
            await conn.commit()

    @property
    def conn(self) -> aiosqlite.Connection:
        """Deprecated — use `transaction()` for writes, `read()` for reads.
        Retained for diagnostic tests only."""
        if self._writer is None:
            raise RuntimeError("SQLiteConnection is not open")
        return self._writer

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        if self._writer is None:
            raise RuntimeError("SQLiteConnection is not open")
        async with self._write_lock:
            try:
                yield self._writer
                await self._writer.commit()
            except BaseException:
                await self._writer.rollback()
                raise

    @asynccontextmanager
    async def read(self) -> AsyncIterator[aiosqlite.Connection]:
        if self._readers is None:
            raise RuntimeError("SQLiteConnection is not open")
        reader = await self._readers.get()
        try:
            yield reader
        finally:
            await self._readers.put(reader)
