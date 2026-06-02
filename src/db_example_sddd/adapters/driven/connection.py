from pathlib import Path

import aiosqlite


async def configure(conn: aiosqlite.Connection) -> None:
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA busy_timeout = 5000")
    await conn.execute("PRAGMA foreign_keys = ON")


async def open_connection(path: Path) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path)
    await configure(conn)
    return conn
