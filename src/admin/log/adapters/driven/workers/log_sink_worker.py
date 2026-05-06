import asyncio
from dataclasses import dataclass, field

import orjson
import structlog

from shared.adapters.driven.db import SQLiteConnection

from ....app.interfaces import ILogBroadcaster

_log = structlog.get_logger(__name__)


_INSERT_SQL = (
    "INSERT INTO logs ("
    "timestamp, level, logger, event, pathname, lineno, func_name, "
    "trace_id, span_id, raw_json"
    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


@dataclass(slots=True, kw_only=True)
class LogSinkWorker:
    """Single-writer queue drainer for the log store.

    One instance per process — SQLite is not safe to fan out writes. Reads
    rendered structlog records off an `asyncio.Queue` and inserts them in
    batches. Persist and broadcast legs run concurrently and are isolated:
    a stuck SSE subscriber must never block the writer, and a write
    failure must not silence the live stream. Per-row JSON decode errors
    are logged and dropped, never fatal.
    """

    _queue: asyncio.Queue[str]
    _connection: SQLiteConnection
    _broadcaster: ILogBroadcaster
    _batch_size: int
    _batch_timeout_ms: int
    # Event, not a flag: stop() is called from another coroutine; the loop
    # must observe the new state without ad-hoc polling races.
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    async def start(self) -> None:
        _log.info(
            "sink worker started",
            batch_size=self._batch_size,
            batch_timeout_ms=self._batch_timeout_ms,
        )
        while not self._stop_event.is_set():
            batch = await self._collect_batch()
            if batch:
                await self._flush(batch)

        remaining = self._drain_queue()
        if remaining:
            _log.info("sink draining tail", remaining=len(remaining))
            await self._flush(remaining)
        _log.info("sink worker stopped")

    def stop(self) -> None:
        self._stop_event.set()

    async def _flush(self, batch: list[str]) -> None:
        insert_result, broadcast_result = await asyncio.gather(
            self._insert_batch(batch),
            self._broadcaster.broadcast_batch(batch),
            return_exceptions=True,
        )
        if isinstance(insert_result, BaseException):
            _log.exception(
                "log persist failed",
                batch_size=len(batch),
                exc_info=insert_result,
            )
        if isinstance(broadcast_result, BaseException):
            _log.exception(
                "log broadcast failed",
                batch_size=len(batch),
                exc_info=broadcast_result,
            )

    def _drain_queue(self) -> list[str]:
        items: list[str] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items

    async def _collect_batch(self) -> list[str]:
        # Block on the first item, then drain the rest non-blockingly until
        # batch fills or the queue empties. A wait_for-per-item loop creates
        # a coroutine + future per element; this keeps it O(1) per batch.
        timeout = self._batch_timeout_ms / 1000
        try:
            first = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return []
        batch: list[str] = [first]
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return batch

    async def _insert_batch(self, batch: list[str]) -> None:
        rows: list[tuple] = []
        for raw in batch:
            try:
                data = orjson.loads(raw)
            except orjson.JSONDecodeError:
                _log.warning(
                    "log payload malformed, dropped",
                    payload_preview=raw[:200],
                )
                continue
            rows.append(
                (
                    data.get("timestamp", ""),
                    data.get("level", "INFO").upper(),
                    data.get("logger"),
                    data.get("event", ""),
                    data.get("pathname"),
                    data.get("lineno"),
                    data.get("func_name"),
                    data.get("trace_id"),
                    data.get("span_id"),
                    raw,
                )
            )

        if not rows:
            return
        async with self._connection.transaction() as db:
            await db.executemany(_INSERT_SQL, rows)
