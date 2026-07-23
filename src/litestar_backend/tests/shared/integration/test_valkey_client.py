import pytest

from shared.adapters.driven.valkey import build_valkey_client


@pytest.mark.asyncio
async def test_valkey_set_get_roundtrip(valkey_url: str) -> None:
    """Given a Valkey container, When set then get, Then the value round-trips."""
    client = build_valkey_client(valkey_url)
    try:
        await client.set("k", "v", ex=10)
        assert await client.get("k") == "v"
    finally:
        await client.aclose()
