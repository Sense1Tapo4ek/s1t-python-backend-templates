from dataclasses import dataclass

import structlog

from ..config import DbExampleSdddConfig
from .driven.migrations_runner import apply_migrations
from .driven.sqlite_pool import SqlitePool

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class DbExampleSdddLifespanManager:
    config: DbExampleSdddConfig
    pool: SqlitePool

    async def start(self) -> None:
        if self.config.db_path is None:
            raise RuntimeError("DB_EXAMPLE_SDDD_DB_PATH could not be resolved")
        await apply_migrations(self.config.db_path)
        await self.pool.open()
        _log.info("db_example_sddd started", db_path=str(self.config.db_path))

    async def stop(self) -> None:
        await self.pool.close()
        _log.info("db_example_sddd stopped")
