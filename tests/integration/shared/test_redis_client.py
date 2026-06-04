import pytest

from shared.adapters.driven.redis import build_redis_client


@pytest.mark.asyncio
async def test_redis_set_get_roundtrip(redis_url: str) -> None:
    """Given a Redis container, When set then get, Then the value round-trips."""
    client = build_redis_client(redis_url)
    try:
        await client.set("k", "v", ex=10)
        assert await client.get("k") == "v"
    finally:
        await client.aclose()
