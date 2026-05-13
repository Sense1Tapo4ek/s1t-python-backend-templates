import pytest
from redis.asyncio import Redis

from admin.metrics.ports.driven.collectors import ValkeyAggregatedCollector

pytestmark = pytest.mark.asyncio


def _samples(metrics, name):
    """Flatten a list of MetricFamily into samples for a given metric name."""
    for fam in metrics:
        if fam.name == name:
            return list(fam.samples)
    return []


class TestValkeyAggregatedCollector:
    async def test_aggregates_per_worker_rss(self, valkey_client: Redis) -> None:
        """
        Given two api workers and one sink reporting rss_bytes,
        When the Collector runs,
        Then three samples are emitted, one per worker_id label.
        """
        await valkey_client.hset("metrics:api:h:1",
                          mapping={"role": "api", "worker_id": "h:1",
                                   "rss_bytes": "100"})
        await valkey_client.hset("metrics:api:h:2",
                          mapping={"role": "api", "worker_id": "h:2",
                                   "rss_bytes": "200"})
        await valkey_client.hset("metrics:sink:h:3",
                          mapping={"role": "sink", "worker_id": "h:3",
                                   "rss_bytes": "300"})

        collector = ValkeyAggregatedCollector(
            _redis=valkey_client, _key_prefix="metrics:",
        )

        metrics = list(await collector.acollect())
        rss = _samples(metrics, "admin_metrics_worker_rss_bytes")
        assert len(rss) == 3
        labels_to_value = {s.labels["worker_id"]: s.value for s in rss}
        assert labels_to_value == {"h:1": 100.0, "h:2": 200.0, "h:3": 300.0}

    async def test_missing_optional_fields_are_skipped(self, valkey_client: Redis) -> None:
        """
        Given a worker hash that only carries identity fields (no rss),
        When the Collector runs,
        Then no rss sample is emitted for that worker (silent skip).
        """
        await valkey_client.hset("metrics:api:h:1",
                          mapping={"role": "api", "worker_id": "h:1"})
        collector = ValkeyAggregatedCollector(
            _redis=valkey_client, _key_prefix="metrics:",
        )
        metrics = list(await collector.acollect())
        assert _samples(metrics, "admin_metrics_worker_rss_bytes") == []

    async def test_redis_failure_yields_empty(self, valkey_client: Redis) -> None:
        """
        Given Valkey unreachable,
        When collector runs,
        Then it yields no samples but raises no exception.
        """
        class _Boom:
            def scan_iter(self, *a, **kw):
                raise RuntimeError("boom")

        collector = ValkeyAggregatedCollector(
            _redis=_Boom(),  # type: ignore[arg-type]
            _key_prefix="metrics:",
        )
        metrics = list(await collector.acollect())
        assert metrics == [] or all(not list(m.samples) for m in metrics)
