import asyncio
from pathlib import Path

import pytest

from shared.adapters.driven.db import SQLiteConnection


@pytest.mark.asyncio
class TestSqliteConnectionLifecycle:
    async def test_open_creates_parent_directory(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "deeper" / "test.db"
        conn = SQLiteConnection(_db_path=db_path)

        await conn.open()

        try:
            assert db_path.parent.is_dir()
            assert db_path.exists()
        finally:
            await conn.close()

    async def test_open_is_idempotent(self, tmp_path: Path) -> None:
        conn = SQLiteConnection(_db_path=tmp_path / "t.db")

        await conn.open()
        first = conn.conn
        await conn.open()
        second = conn.conn

        try:
            assert first is second
        finally:
            await conn.close()

    async def test_conn_property_raises_before_open(self, tmp_path: Path) -> None:
        conn = SQLiteConnection(_db_path=tmp_path / "t.db")

        with pytest.raises(RuntimeError, match="not open"):
            _ = conn.conn

    async def test_transaction_commits_on_success(self, tmp_path: Path) -> None:
        conn = SQLiteConnection(_db_path=tmp_path / "t.db")
        await conn.open()
        try:
            async with conn.transaction() as db:
                await db.execute("CREATE TABLE x (id INTEGER, v TEXT)")
                await db.execute("INSERT INTO x VALUES (1, 'a')")

            async with conn.conn.execute("SELECT v FROM x WHERE id = 1") as cur:
                row = await cur.fetchone()
            assert row[0] == "a"
        finally:
            await conn.close()

    async def test_transaction_rolls_back_on_exception(self, tmp_path: Path) -> None:
        conn = SQLiteConnection(_db_path=tmp_path / "t.db")
        await conn.open()
        try:
            async with conn.transaction() as db:
                await db.execute("CREATE TABLE x (id INTEGER)")

            with pytest.raises(RuntimeError, match="boom"):
                async with conn.transaction() as db:
                    await db.execute("INSERT INTO x VALUES (1)")
                    raise RuntimeError("boom")

            async with conn.conn.execute("SELECT count(*) FROM x") as cur:
                row = await cur.fetchone()
            assert row[0] == 0
        finally:
            await conn.close()

    async def test_read_runs_concurrent_with_write(self, tmp_path: Path) -> None:
        """
        Given an open connection with a populated table,
        When a long-ish write transaction overlaps with a read,
        Then the read does not raise 'database is locked' (WAL + reader pool).
        """
        conn = SQLiteConnection(_db_path=tmp_path / "t.db", _reader_count=2)
        await conn.open()
        try:
            async with conn.transaction() as db:
                await db.execute("CREATE TABLE x (id INTEGER, v TEXT)")
                await db.executemany(
                    "INSERT INTO x VALUES (?, ?)",
                    [(i, f"v{i}") for i in range(10)],
                )

            async def writer() -> None:
                async with conn.transaction() as db:
                    await db.execute("INSERT INTO x VALUES (100, 'late')")
                    await asyncio.sleep(0.1)

            async def reader() -> int:
                async with conn.read() as db:
                    async with db.execute("SELECT count(*) FROM x") as cur:
                        row = await cur.fetchone()
                return row[0]

            _, count = await asyncio.gather(writer(), reader())
            assert count >= 10
        finally:
            await conn.close()

    async def test_read_pool_is_bounded(self, tmp_path: Path) -> None:
        """
        Given _reader_count=1,
        When two reads are requested concurrently,
        Then the second waits for the first to release the reader.
        """
        conn = SQLiteConnection(_db_path=tmp_path / "t.db", _reader_count=1)
        await conn.open()
        try:
            async with conn.transaction() as db:
                await db.execute("CREATE TABLE x (id INTEGER)")
                await db.execute("INSERT INTO x VALUES (1)")

            order: list[str] = []

            async def slow_reader() -> None:
                async with conn.read() as db:
                    order.append("a-in")
                    await asyncio.sleep(0.05)
                    async with db.execute("SELECT 1") as cur:
                        await cur.fetchone()
                    order.append("a-out")

            async def fast_reader() -> None:
                await asyncio.sleep(0.01)
                async with conn.read():
                    order.append("b-in")

            await asyncio.gather(slow_reader(), fast_reader())
            assert order == ["a-in", "a-out", "b-in"]
        finally:
            await conn.close()

    async def test_close_is_idempotent(self, tmp_path: Path) -> None:
        conn = SQLiteConnection(_db_path=tmp_path / "t.db")
        await conn.open()
        await conn.close()
        await conn.close()
