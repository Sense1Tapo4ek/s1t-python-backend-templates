from dataclasses import dataclass

import asyncpg
import structlog

from .driven.migrations_runner import apply_migrations

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class DbExampleSdddLifespanManager:
    pool: asyncpg.Pool
    yoyo_url: str

    async def start(self) -> None:
        await apply_migrations(self.yoyo_url)
        _log.info("db_example_sddd started")

    async def stop(self) -> None:
        await self.pool.close()
        _log.info("db_example_sddd stopped")
