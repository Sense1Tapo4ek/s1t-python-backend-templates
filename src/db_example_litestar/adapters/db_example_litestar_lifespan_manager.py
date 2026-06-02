from dataclasses import dataclass

import structlog
from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy.ext.asyncio import AsyncEngine

# Imported for the side effect of registering the ORM tables on
# UUIDAuditBase.metadata before create_all runs (no direct use of the symbols).
from ..ports import orm_models  # noqa: F401

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class DbExampleLitestarLifespanManager:
    engine: AsyncEngine

    async def start(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(UUIDAuditBase.metadata.create_all)
        _log.info("db_example_litestar started")

    async def stop(self) -> None:
        await self.engine.dispose()
        _log.info("db_example_litestar stopped")
