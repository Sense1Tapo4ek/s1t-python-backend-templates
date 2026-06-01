from dataclasses import dataclass

import structlog

from ..config import DbExampleConfig
from .driven.db.migrations_runner import apply_migrations
from .driven.db.sqlite_pool import SqlitePool

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class DbExampleLifespanManager:
    config: DbExampleConfig
    pool: SqlitePool

    async def start(self) -> None:
        if self.config.db_path is None:
            raise RuntimeError("DB_EXAMPLE_DB_PATH could not be resolved")
        await apply_migrations(self.config.db_path)
        await self.pool.open()
        _log.info("db_example started", db_path=str(self.config.db_path))

    async def stop(self) -> None:
        await self.pool.close()
        _log.info("db_example stopped")
