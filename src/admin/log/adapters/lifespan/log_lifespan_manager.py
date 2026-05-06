"""Lifecycle orchestration for the admin/log subsystem.

Owns startup/shutdown of every infrastructure piece this context needs:
SQLite migrations, the connection pool, and the background workers (sink,
cleanup). Sits at `adapters/lifespan/` (alongside `adapters/middleware/`)
because it is "neither driving nor driven" — invoked from outside via
the root lifespan handler, but its work is to orchestrate driven infra
(yoyo, aiosqlite, background workers).
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from yoyo import get_backend, read_migrations

from shared.adapters.driven.db import SQLiteConnection

from ...config import YOYO_MIGRATION_TABLE
from ..driven.workers import LogCleanupWorker, LogSinkWorker

# Per-task wait budget on shutdown. Workers honor a stop event and finish
# in milliseconds in the happy path; this bounds the worst case where a
# task is wedged in a system call before forced cancellation.
_GRACEFUL_STOP_TIMEOUT_S = 5.0

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class LogLifespanManager:
    """Owns start/stop sequencing for the log subsystem.

    Single instance, lives in the DI container. On `start()`: applies yoyo
    migrations, opens the SQLite connection, and spawns the sink and
    cleanup workers. On `stop()`: signals workers, waits up to
    `_GRACEFUL_STOP_TIMEOUT_S` per task, force-cancels the rest, then
    closes the connection.
    """

    _connection: SQLiteConnection
    _sink_worker: LogSinkWorker
    _cleanup_worker: LogCleanupWorker
    _db_path: Path
    _migrations_path: Path
    _tasks: list[asyncio.Task] = field(default_factory=list)

    async def start(self) -> None:
        _log.info("migrations applying", path=str(self._migrations_path))
        applied = await asyncio.to_thread(self._apply_migrations)
        _log.info("migrations applied", applied=applied, db_path=str(self._db_path))

        await self._connection.open()
        _log.info("log db opened", db_path=str(self._db_path))

        self._tasks.append(
            asyncio.create_task(self._sink_worker.start(), name="log-sink"),
        )
        self._tasks.append(
            asyncio.create_task(self._cleanup_worker.run(), name="log-cleanup"),
        )
        _log.info("log workers started", count=len(self._tasks))

    def _apply_migrations(self) -> int:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        backend = get_backend(
            f"sqlite:///{self._db_path}",
            migration_table=YOYO_MIGRATION_TABLE,
        )
        migrations = read_migrations(str(self._migrations_path))
        with backend, backend.lock():
            # `to_apply` returns yoyo's MigrationList, not a plain list;
            # `apply_migrations` reads `.post_apply` off it.
            pending = backend.to_apply(migrations)
            count = len(pending)
            backend.apply_migrations(pending)
            return count

    async def stop(self) -> None:
        _log.info("log workers stopping", count=len(self._tasks))
        self._sink_worker.stop()
        self._cleanup_worker.stop()
        if self._tasks:
            _done, pending = await asyncio.wait(
                self._tasks,
                timeout=_GRACEFUL_STOP_TIMEOUT_S,
            )
            for task in pending:
                _log.warning("log worker forced cancel", task=task.get_name())
                task.cancel()
            for task in pending:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._tasks.clear()
        await self._connection.close()
        _log.info("log db closed")
