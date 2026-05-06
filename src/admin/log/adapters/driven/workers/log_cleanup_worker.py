import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import structlog

from shared.adapters.driven.db import SQLiteConnection

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class LogCleanupWorker:
    """Periodic retention worker.

    Deletes rows older than `_retention_days`, then runs
    `PRAGMA wal_checkpoint(TRUNCATE)` and `PRAGMA optimize` in a separate
    short transaction so the read-stall window stays bounded. Designed to
    coexist with the sink writer — never holds a write lock during the
    checkpoint.
    """

    _connection: SQLiteConnection
    _retention_days: int
    _interval_hours: int
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    async def run(self) -> None:
        _log.info(
            "cleanup worker started",
            retention_days=self._retention_days,
            interval_hours=self._interval_hours,
        )
        while not self._stop_event.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval_hours * 3600,
                )

            if self._stop_event.is_set():
                break

            cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)
            async with self._connection.transaction() as db:
                cur = await db.execute(
                    "DELETE FROM logs WHERE timestamp < ?",
                    (cutoff.isoformat(),),
                )
                deleted = cur.rowcount or 0
            # Checkpoint AFTER the DELETE commit. wal_checkpoint(TRUNCATE)
            # needs an EXCLUSIVE lock and waits out active readers; running
            # it inside the DELETE transaction held that lock for the full
            # checkpoint duration and starved SSE/export readers. A
            # separate write-lock window keeps the read-stall window short.
            # `PRAGMA optimize` refreshes sqlite_stat tables so the planner
            # picks the right index after the row distribution shifts post-
            # delete; cheap (microseconds) when no work is needed.
            async with self._connection.transaction() as db:
                await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                await db.execute("PRAGMA optimize")
            _log.info(
                "cleanup pass complete",
                deleted=deleted,
                cutoff=cutoff.isoformat(),
            )
        _log.info("cleanup worker stopped")

    def stop(self) -> None:
        self._stop_event.set()
