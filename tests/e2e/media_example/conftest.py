from collections.abc import AsyncIterator

import pytest_asyncio
import redis.asyncio as aioredis

from shared.adapters.driven.valkey import build_valkey_client


@pytest_asyncio.fixture
async def valkey(valkey_url: str) -> AsyncIterator[aioredis.Redis]:
    """Function-scoped Valkey client for e2e stream assertions.

    Function scope ensures teardown runs in the same event loop as the test.
    Requests `valkey_url` (session fixture) directly so the URL is
    resolved before _isolate_environment deletes VALKEY_URL from environ.
    """
    client: aioredis.Redis = build_valkey_client(valkey_url)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
