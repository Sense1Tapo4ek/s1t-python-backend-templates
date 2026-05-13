"""Integration-test infrastructure shared across contexts.

Provides a session-scoped Valkey container plus a function-scoped Redis
client that flushes between tests so each test sees a clean keyspace.
The container starts once per pytest session — Docker pulls + boots add
about a second, which we amortise across every integration test that
touches Valkey/Redis.

Replaces the previous `fakeredis` based fixtures: real Valkey catches
Streams / pipeline / TTL semantics that the in-memory emulator does
not (XAUTOCLAIM ordering, ms-precision PEXPIRE, scan cursor reuse).
"""

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def valkey_container() -> Iterator[RedisContainer]:
    """Start one Valkey-compatible container for the whole session.

    Uses the `valkey/valkey` image so behaviour matches production. The
    `testcontainers` Redis adapter speaks the same protocol — there is
    no Valkey-specific module.
    """
    with RedisContainer("valkey/valkey:8-alpine") as container:
        yield container


@pytest_asyncio.fixture
async def valkey_client(
    valkey_container: RedisContainer,
) -> AsyncIterator[Redis]:
    """Per-test async Redis client. Issues FLUSHDB before yielding.

    Decoding stays off (`decode_responses=False`) to match how the
    production codebase reads bytes from hashes.
    """
    host = valkey_container.get_container_host_ip()
    port = valkey_container.get_exposed_port(6379)
    client: Redis = Redis(host=host, port=int(port), decode_responses=False)
    try:
        await client.flushdb()
        yield client
    finally:
        await client.aclose()
