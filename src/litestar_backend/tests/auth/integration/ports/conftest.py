from collections.abc import AsyncIterator

import pytest_asyncio
import redis.asyncio as aioredis

from shared.adapters.driven.valkey import build_valkey_client


@pytest_asyncio.fixture
async def valkey(valkey_url: str) -> AsyncIterator[aioredis.Redis]:
    client: aioredis.Redis = build_valkey_client(valkey_url)
    try:
        await client.flushdb()
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
