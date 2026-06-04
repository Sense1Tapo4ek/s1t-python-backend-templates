from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio
import redis.asyncio as aioredis

from media_example.adapters.driven.migrations_runner import apply_migrations
from shared.adapters.driven.valkey import build_valkey_client

_SCHEMA = "media"


@pytest_asyncio.fixture(scope="module")
async def _migrated(pg_dsn: str) -> None:
    yoyo_url = pg_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    await apply_migrations(yoyo_url)


@pytest_asyncio.fixture
async def conn(pg_dsn: str, _migrated: None) -> AsyncIterator[asyncpg.Connection]:
    c = await asyncpg.connect(pg_dsn, server_settings={"search_path": _SCHEMA})
    tr = c.transaction()
    await tr.start()
    try:
        yield c
    finally:
        await tr.rollback()
        await c.close()


@pytest_asyncio.fixture
async def valkey(valkey_url: str) -> AsyncIterator[aioredis.Redis]:
    client: aioredis.Redis = build_valkey_client(valkey_url)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
