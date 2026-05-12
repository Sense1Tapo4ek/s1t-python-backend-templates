import pytest
import pytest_asyncio
import fakeredis.aioredis

from admin.metrics.domain import Severity
from admin.metrics.ports.driven.plugins import WorkersMetricsPlugin
from tests.conftest_helpers.plugin_contract import assert_plugin_contract

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    try:
        yield r
    finally:
        await r.aclose()


class TestWorkersMetricsPlugin:
    async def test_summary_counts_alive(self, redis) -> None:
        """
        Given 2 api + 1 sink hashes,
        When summary() runs,
        Then it reports alive=3 with role breakdown.
        """
        for k, role in (("metrics:api:h:1", "api"), ("metrics:api:h:2", "api"),
                        ("metrics:sink:h:3", "sink")):
            await redis.hset(k, mapping={
                "role": role, "worker_id": k.rsplit(":", 2)[-2] + ":" + k.rsplit(":", 1)[-1],
                "rss_bytes": "100", "loop_lag_p95_ms": "1.0",
                "started_at": "2026-05-12T12:00:00+00:00",
            })

        plugin = WorkersMetricsPlugin(
            _redis=redis, _key_prefix="metrics:",
        )
        s = await plugin.summary()
        # alive KV is first
        assert s.kvs[0].label == "alive"
        assert "3" in s.kvs[0].value

    async def test_detail_lists_each_worker(self, redis) -> None:
        """
        Given a single worker hash in Redis,
        When detail() is called,
        Then sections contain a rows list with the worker's data.
        """
        await redis.hset("metrics:api:h:1", mapping={
            "role": "api", "worker_id": "h:1",
            "rss_bytes": "100", "loop_lag_p95_ms": "2.5",
            "started_at": "2026-05-12T12:00:00+00:00",
        })
        plugin = WorkersMetricsPlugin(_redis=redis, _key_prefix="metrics:")
        d = await plugin.detail()
        assert d.sections, "detail must have at least the worker-list section"
        payload = d.sections[0].payload
        assert payload["rows"], "rows non-empty"
        first = payload["rows"][0]
        assert first["worker_id"] == "h:1"
        assert first["rss_bytes"] == 100

    async def test_rss_above_warn_threshold_marked_warn(self, redis) -> None:
        """
        Given a worker with RSS above the warn threshold,
        When detail() is called,
        Then the row's rss_severity is WARN.
        """
        await redis.hset("metrics:api:h:1", mapping={
            "role": "api", "worker_id": "h:1",
            "rss_bytes": str(300 * 1024 * 1024), "loop_lag_p95_ms": "0",
            "started_at": "2026-05-12T12:00:00+00:00",
        })
        plugin = WorkersMetricsPlugin(_redis=redis, _key_prefix="metrics:")
        d = await plugin.detail()
        # Look up the row's rss severity from payload
        row = d.sections[0].payload["rows"][0]
        assert row["rss_severity"] == Severity.WARN.value

    async def test_contract(self, redis) -> None:
        """
        Given a plugin with one worker hash,
        When assert_plugin_contract runs,
        Then all contract assertions pass.
        """
        await redis.hset("metrics:api:h:1", mapping={
            "role": "api", "worker_id": "h:1",
            "rss_bytes": "100", "loop_lag_p95_ms": "0",
            "started_at": "2026-05-12T12:00:00+00:00",
        })
        plugin = WorkersMetricsPlugin(_redis=redis, _key_prefix="metrics:")
        await assert_plugin_contract(plugin)
