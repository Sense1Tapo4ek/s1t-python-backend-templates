from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from advanced_alchemy.base import UUIDAuditBase

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class DbExampleAlchemyLifespanManager:
    engine: AsyncEngine

    async def start(self) -> None:
        # Import models so they register with UUIDAuditBase.metadata before create_all.
        import db_example_alchemy.adapters.driven.db.orm_models  # noqa: F401

        async with self.engine.begin() as conn:
            await conn.run_sync(UUIDAuditBase.metadata.create_all)
        _log.info("db_example_alchemy started")

    async def stop(self) -> None:
        await self.engine.dispose()
        _log.info("db_example_alchemy stopped")
