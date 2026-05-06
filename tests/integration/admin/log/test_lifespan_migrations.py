import asyncio
import sqlite3
from pathlib import Path

import pytest
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

from admin.log.adapters.driven.workers import LogCleanupWorker, LogSinkWorker
from admin.log.adapters.lifespan import LogLifespanManager
from admin.log.config import YOYO_MIGRATION_TABLE
from admin.log.ports.driven.dispatchers import ChannelsLogBroadcaster
from shared.adapters.driven.db import SQLiteConnection

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MIGRATIONS = _REPO_ROOT / "migrations" / "admin_log"


def _make_manager(db_path: Path) -> LogLifespanManager:
    """Build a real LogLifespanManager wired to a tmp DB."""
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    connection = SQLiteConnection(_db_path=db_path)
    channels = ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )
    broadcaster = ChannelsLogBroadcaster(_channels=channels)
    sink = LogSinkWorker(
        _queue=queue,
        _connection=connection,
        _batch_size=10,
        _batch_timeout_ms=10,
        _broadcaster=broadcaster,
    )
    cleanup = LogCleanupWorker(
        _connection=connection,
        _retention_days=7,
        _interval_hours=24,
    )
    return LogLifespanManager(
        _connection=connection,
        _sink_worker=sink,
        _cleanup_worker=cleanup,
        _db_path=db_path,
        _migrations_path=_MIGRATIONS,
    )


def _read_schema(db_path: Path) -> dict[str, list[str]]:
    """Return {table_name: [column_names]} for the sqlite db at path."""
    conn = sqlite3.connect(db_path)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table','virtual') "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return {
            t: [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
            for t in tables
        }
    finally:
        conn.close()


def _count_revisions(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            f"SELECT count(*) FROM {YOYO_MIGRATION_TABLE}"
        ).fetchone()[0]
    finally:
        conn.close()


@pytest.mark.asyncio
class TestLifespanMigrations:
    async def test_start_applies_migrations_then_opens_connection(
        self,
        tmp_path: Path,
    ) -> None:
        """
        Given a fresh tmp directory,
        When the lifespan manager starts,
        Then the schema is applied, the yoyo migration table records the
        revisions, and the connection is open with WAL pragma.
        """
        db_path = tmp_path / "logs" / "admin_logs.db"
        manager = _make_manager(db_path)

        await manager.start()

        try:
            schema = _read_schema(db_path)
            assert "logs" in schema
            assert "trace_id" in schema["logs"]
            assert "span_id" in schema["logs"]
            assert YOYO_MIGRATION_TABLE in schema
            assert "logs_fts" in schema

            async with manager._connection.conn.execute(
                "PRAGMA journal_mode"
            ) as cur:
                row = await cur.fetchone()
            assert row[0].lower() == "wal"
        finally:
            await manager.stop()

    async def test_restart_is_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "logs" / "admin_logs.db"

        first = _make_manager(db_path)
        await first.start()
        await first.stop()

        before = _read_schema(db_path)
        revisions_before = _count_revisions(db_path)

        second = _make_manager(db_path)
        await second.start()
        try:
            after = _read_schema(db_path)
            revisions_after = _count_revisions(db_path)

            assert before == after
            assert revisions_before == revisions_after
        finally:
            await second.stop()

    async def test_start_creates_missing_parent_directory(
        self,
        tmp_path: Path,
    ) -> None:
        db_path = tmp_path / "deep" / "nested" / "admin.db"
        manager = _make_manager(db_path)

        await manager.start()

        try:
            assert db_path.parent.is_dir()
            assert db_path.exists()
        finally:
            await manager.stop()
