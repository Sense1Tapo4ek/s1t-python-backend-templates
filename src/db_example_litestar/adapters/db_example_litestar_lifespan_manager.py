from dataclasses import dataclass

import structlog
from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy.ext.asyncio import AsyncEngine

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class DbExampleLitestarLifespanManager:
    engine: AsyncEngine

    async def start(self) -> None:
        # Import the domain models so they register with UUIDAuditBase.metadata
        # before create_all. The one place an adapter reaches into domain -- a
        # pure side-effect import for table registration, no use of the types.
        import db_example_litestar.domain  # noqa: F401

        async with self.engine.begin() as conn:
            await conn.run_sync(UUIDAuditBase.metadata.create_all)
        _log.info("db_example_litestar started")

    async def stop(self) -> None:
        await self.engine.dispose()
        _log.info("db_example_litestar stopped")
