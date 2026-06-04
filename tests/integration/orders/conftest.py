import asyncpg
import pytest_asyncio

from orders.adapters.driven.migrations_runner import apply_migrations

_SCHEMA = "orders"


@pytest_asyncio.fixture(scope="module")
async def _migrated(pg_dsn: str) -> None:
    yoyo_url = pg_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    await apply_migrations(yoyo_url)


@pytest_asyncio.fixture
async def conn(pg_dsn: str, _migrated: None):
    c = await asyncpg.connect(pg_dsn, server_settings={"search_path": _SCHEMA})
    tr = c.transaction()
    await tr.start()
    try:
        yield c
    finally:
        await tr.rollback()
        await c.close()
