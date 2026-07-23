from collections.abc import AsyncIterator

import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.driven.postgres import build_engine, build_sessionmaker, run_migrations
from shared.adapters.driven.valkey import build_valkey_client
from shared.generics.config import PROJECT_ROOT

_SCHEMA = "media"
_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "media")


@pytest_asyncio.fixture(scope="module")
async def _migrated(pg_dsn: str) -> None:
    yoyo_url = pg_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    await run_migrations(yoyo_url, _MIGRATIONS_DIR)


@pytest_asyncio.fixture
async def session(pg_dsn: str, _migrated: None) -> AsyncIterator[AsyncSession]:
    alchemy_url = pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = build_engine(alchemy_url, _SCHEMA)
    sm = build_sessionmaker(engine)
    async with sm() as s:
        await s.begin()
        try:
            yield s
        finally:
            await s.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def valkey(valkey_url: str) -> AsyncIterator[aioredis.Redis]:
    client: aioredis.Redis = build_valkey_client(valkey_url)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
