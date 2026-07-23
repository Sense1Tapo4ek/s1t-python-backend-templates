from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from media_processing.ports.driven import ValkeyInboxStore


@pytest_asyncio.fixture
async def valkey(valkey_url: str):
    client = aioredis.from_url(valkey_url, decode_responses=True)
    yield client
    await client.aclose()


class TestValkeyInboxStore:
    @pytest.mark.asyncio
    async def test_mark_then_seen(self, valkey) -> None:
        """Given an unseen event, When marked, Then seen() flips False -> True."""
        # Arrange
        store = ValkeyInboxStore(_valkey=valkey, _ttl_seconds=60)
        event_id = uuid4()

        # Act / Assert
        assert await store.seen(event_id) is False
        await store.mark_processed(event_id)
        assert await store.seen(event_id) is True

    @pytest.mark.asyncio
    async def test_distinct_events_are_independent(self, valkey) -> None:
        """Given one marked event, When checking another, Then it is unseen."""
        store = ValkeyInboxStore(_valkey=valkey, _ttl_seconds=60)
        a, b = uuid4(), uuid4()
        await store.mark_processed(a)
        assert await store.seen(b) is False
