import pytest
import redis.asyncio as aioredis

from auth.ports.driven import ValkeyDenylist


@pytest.mark.asyncio
class TestValkeyDenylist:
    async def test_unknown_jti_is_not_contained(self, valkey: aioredis.Redis) -> None:
        """Given an empty denylist, When checking a jti, Then it is absent."""
        store = ValkeyDenylist(_valkey=valkey)
        assert await store.contains("never-added") is False

    async def test_added_jti_is_contained(self, valkey: aioredis.Redis) -> None:
        """Given an added jti, When checking it, Then it is present."""
        store = ValkeyDenylist(_valkey=valkey)
        await store.add("jti-1", ttl_seconds=60)
        assert await store.contains("jti-1") is True

    async def test_nonpositive_ttl_is_noop(self, valkey: aioredis.Redis) -> None:
        """Given a non-positive ttl, When adding, Then nothing is stored."""
        store = ValkeyDenylist(_valkey=valkey)
        await store.add("jti-expired", ttl_seconds=0)
        assert await store.contains("jti-expired") is False
