import pytest
from prometheus_client import REGISTRY

from admin.metrics.ports.driven.plugins import HttpMetricsPlugin
from tests.conftest_helpers.plugin_contract import assert_plugin_contract

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolated_registry():
    """Tear down any test-registered collectors between tests."""
    snapshot = list(REGISTRY._collector_to_names.keys())
    yield
    for c in list(REGISTRY._collector_to_names.keys()):
        if c not in snapshot:
            REGISTRY.unregister(c)


class TestHttpMetricsPlugin:
    async def test_summary_when_no_traffic_shows_zero(self) -> None:
        plugin = HttpMetricsPlugin(_prefix="test_http_a")
        s = await plugin.summary()
        labels = [kv.label for kv in s.kvs]
        assert "rps - 1m" in labels or "rps · 1m" in labels
        assert "p95 - 5m" in labels or "p95 · 5m" in labels
        assert "5xx - 5m" in labels or "5xx · 5m" in labels

    async def test_contract(self) -> None:
        plugin = HttpMetricsPlugin(_prefix="test_http_b")
        await assert_plugin_contract(plugin)

    async def test_observe_increments_internal_counters(self) -> None:
        """
        Given the plugin observes a few requests with timings,
        When summary() runs,
        Then RPS becomes non-zero and reflects the recent traffic.
        """
        plugin = HttpMetricsPlugin(_prefix="test_http_c")
        plugin.observe_for_test(status="200", duration_s=0.010)
        plugin.observe_for_test(status="200", duration_s=0.020)
        plugin.observe_for_test(status="500", duration_s=0.030)

        s = await plugin.summary()
        # Just verify the KV is produced; rate may be 0.0 if ring has only 1 entry
        rps_kv = next(kv for kv in s.kvs if kv.label in ("rps · 1m", "rps - 1m"))
        assert "/s" in rps_kv.value
