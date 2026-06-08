from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from media_processing.domain import JobKind
from media_processing.ports.driven import ValkeyJoinStore


@pytest_asyncio.fixture
async def valkey(valkey_url: str):
    client = aioredis.from_url(valkey_url, decode_responses=True)
    yield client
    await client.aclose()


class TestValkeyJoinStore:
    @pytest.mark.asyncio
    async def test_add_progresses_and_is_idempotent(self, valkey) -> None:
        """Given distinct then repeated kinds, When added, Then count rises to 3 then holds."""
        # Arrange
        store = ValkeyJoinStore(_valkey=valkey, _ttl_seconds=60)
        vid = uuid4()

        # Act / Assert
        assert await store.add(vid, JobKind.STT) == 1
        assert await store.add(vid, JobKind.PLAGIARISM) == 2
        assert await store.add(vid, JobKind.TRANSCODE) == 3
        assert await store.add(vid, JobKind.STT) == 3  # redelivery: idempotent

    @pytest.mark.asyncio
    async def test_clear_removes_the_key(self, valkey) -> None:
        """Given a populated join, When cleared, Then the key is gone."""
        # Arrange
        store = ValkeyJoinStore(_valkey=valkey, _ttl_seconds=60)
        vid = uuid4()
        await store.add(vid, JobKind.STT)

        # Act
        await store.clear(vid)

        # Assert
        assert await valkey.exists(f"join:{vid}") == 0
