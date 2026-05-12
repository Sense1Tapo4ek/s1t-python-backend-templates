import fakeredis.aioredis
import pytest
import pytest_asyncio

from admin.metrics.domain import WorkerIdVo
from admin.metrics.ports.driven.dispatchers import RedisMetricsPublisher

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    try:
        yield r
    finally:
        await r.aclose()


class TestRedisMetricsPublisher:
    async def test_publish_writes_hash_with_ttl(self, redis) -> None:
        """
        Given a worker id and a fields dict,
        When publish() runs,
        Then a hash is written at metrics:<role>:<wid> with the right
        fields and a TTL close to key_ttl_s.
        """
        publisher = RedisMetricsPublisher(
            _redis=redis,
            _key_prefix="metrics:",
            _key_ttl_s=30,
        )
        wid = WorkerIdVo(host="host42", pid=12345)

        await publisher.publish(wid, role="api", fields={"rss_bytes": "123"})

        raw = await redis.hgetall("metrics:api:host42:12345")
        assert raw[b"rss_bytes"] == b"123"
        assert raw[b"role"] == b"api"
        assert raw[b"worker_id"] == b"host42:12345"
        ttl = await redis.ttl("metrics:api:host42:12345")
        assert 25 <= ttl <= 30

    async def test_publish_failure_is_swallowed(self, redis) -> None:
        """
        Given a Redis client that raises on hset,
        When publish() runs,
        Then no exception escapes — metrics MUST never crash the
        process they observe.
        """
        class _Boom:
            def pipeline(self, transaction=False):  # mimic redis-py
                raise RuntimeError("boom")

            async def aclose(self): pass

        publisher = RedisMetricsPublisher(
            _redis=_Boom(),  # type: ignore[arg-type]
            _key_prefix="metrics:",
            _key_ttl_s=30,
        )
        await publisher.publish(
            WorkerIdVo(host="h", pid=1), role="api", fields={"x": "1"}
        )  # must not raise
