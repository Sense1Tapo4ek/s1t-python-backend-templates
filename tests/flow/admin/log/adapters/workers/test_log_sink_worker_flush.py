import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from admin.log.adapters.driven.workers.log_sink_worker import LogSinkWorker


def _slow_connection(insert_delay: float = 0.0):
    """Build a SQLiteConnection-shaped mock whose transaction() yields a db
    that sleeps inside executemany."""
    db = AsyncMock()

    async def slow_executemany(_sql, _rows):
        await asyncio.sleep(insert_delay)

    db.executemany = slow_executemany

    @asynccontextmanager
    async def transaction():
        yield db

    conn = AsyncMock()
    conn.transaction = transaction
    return conn


@pytest.mark.asyncio
class TestLogSinkWorkerFlushParallel:
    async def test_flush_starts_both_legs_before_either_completes(self) -> None:
        """
        Given a flush in progress,
        When the worker enters the gather block,
        Then BOTH legs are in flight before either finishes.

        Sequential execution would let leg #1 finish before leg #2 starts;
        we observe by recording entry order against a shared event.
        """
        insert_started = asyncio.Event()
        broadcast_started = asyncio.Event()
        # Each leg blocks on the OTHER leg's "started" event. With sequential
        # execution this would deadlock; with parallel gather, both fire.
        release = asyncio.Event()

        async def insert_leg(_sql, _rows):
            insert_started.set()
            await broadcast_started.wait()
            release.set()

        db = AsyncMock()
        db.executemany = insert_leg

        @asynccontextmanager
        async def transaction():
            yield db

        conn = AsyncMock()
        conn.transaction = transaction

        async def broadcast_leg(_items):
            broadcast_started.set()
            await insert_started.wait()

        broadcaster = AsyncMock()
        broadcaster.broadcast_batch = broadcast_leg

        worker = LogSinkWorker(
            _queue=asyncio.Queue(),
            _connection=conn,
            _broadcaster=broadcaster,
            _batch_size=10,
            _batch_timeout_ms=10,
        )

        await asyncio.wait_for(
            worker._flush(['{"event":"x","level":"INFO","timestamp":"t"}']),
            timeout=1.0,
        )

        assert insert_started.is_set()
        assert broadcast_started.is_set()
        assert release.is_set()

    async def test_flush_calls_broadcast_batch_with_full_batch(self) -> None:
        """
        Given a batch of 3 items,
        When _flush runs,
        Then broadcast_batch receives the entire list once.
        """
        broadcaster = AsyncMock()
        worker = LogSinkWorker(
            _queue=asyncio.Queue(),
            _connection=_slow_connection(),
            _broadcaster=broadcaster,
            _batch_size=10,
            _batch_timeout_ms=10,
        )

        batch = [
            '{"event":"a","level":"INFO","timestamp":"t"}',
            '{"event":"b","level":"INFO","timestamp":"t"}',
            '{"event":"c","level":"INFO","timestamp":"t"}',
        ]
        await worker._flush(batch)

        broadcaster.broadcast_batch.assert_awaited_once_with(batch)


@pytest.mark.asyncio
class TestLogSinkWorkerFailureIsolation:
    async def test_broadcast_failure_does_not_block_persistence(self) -> None:
        """
        Given a broadcaster that always raises,
        When _flush runs,
        Then executemany still runs to completion (DB write is independent).
        """
        broadcaster = AsyncMock()
        broadcaster.broadcast_batch.side_effect = RuntimeError("channels down")

        executed = asyncio.Event()

        async def record_executemany(_sql, _rows):
            executed.set()

        db = AsyncMock()
        db.executemany = record_executemany

        @asynccontextmanager
        async def transaction():
            yield db

        conn = AsyncMock()
        conn.transaction = transaction

        worker = LogSinkWorker(
            _queue=asyncio.Queue(),
            _connection=conn,
            _broadcaster=broadcaster,
            _batch_size=10,
            _batch_timeout_ms=10,
        )

        await worker._flush(['{"event":"x","level":"INFO","timestamp":"t"}'])

        assert executed.is_set(), "DB write was cancelled by broadcaster failure"

    async def test_persistence_failure_does_not_block_broadcast(self) -> None:
        """
        Given an executemany that always raises,
        When _flush runs,
        Then broadcast_batch still receives the batch.
        """
        broadcaster = AsyncMock()

        db = AsyncMock()
        db.executemany.side_effect = RuntimeError("disk full")

        @asynccontextmanager
        async def transaction():
            yield db

        conn = AsyncMock()
        conn.transaction = transaction

        worker = LogSinkWorker(
            _queue=asyncio.Queue(),
            _connection=conn,
            _broadcaster=broadcaster,
            _batch_size=10,
            _batch_timeout_ms=10,
        )

        await worker._flush(['{"event":"x","level":"INFO","timestamp":"t"}'])

        broadcaster.broadcast_batch.assert_awaited_once()


@pytest.mark.asyncio
class TestLogSinkWorkerMalformedPayload:
    async def test_malformed_row_is_dropped_and_others_persisted(self) -> None:
        captured: list[tuple] = []

        async def capture_executemany(_sql, rows):
            captured.extend(rows)

        db = AsyncMock()
        db.executemany = capture_executemany

        @asynccontextmanager
        async def transaction():
            yield db

        conn = AsyncMock()
        conn.transaction = transaction

        worker = LogSinkWorker(
            _queue=asyncio.Queue(),
            _connection=conn,
            _broadcaster=AsyncMock(),
            _batch_size=10,
            _batch_timeout_ms=10,
        )

        await worker._insert_batch([
            '{"event":"good","level":"INFO","timestamp":"t"}',
            "definitely not json",
            '{"event":"good2","level":"WARN","timestamp":"t"}',
        ])

        assert len(captured) == 2
        events = [row[3] for row in captured]
        assert events == ["good", "good2"]

    async def test_all_malformed_skips_executemany_entirely(self) -> None:
        db = AsyncMock()

        @asynccontextmanager
        async def transaction():
            yield db

        conn = AsyncMock()
        conn.transaction = transaction

        worker = LogSinkWorker(
            _queue=asyncio.Queue(),
            _connection=conn,
            _broadcaster=AsyncMock(),
            _batch_size=10,
            _batch_timeout_ms=10,
        )

        await worker._insert_batch(["bad1", "bad2"])

        db.executemany.assert_not_called()
