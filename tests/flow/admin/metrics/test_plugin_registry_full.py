import pytest
from dishka import make_async_container
from prometheus_client import REGISTRY

from admin.log.provider import AdminLogWebProvider
from admin.metrics.app.interfaces import IModulePluginRegistry
from admin.metrics.provider import AdminMetricsProvider
from shared.provider import SharedProvider

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolated_registry():
    snapshot = list(REGISTRY._collector_to_names.keys())
    yield
    for c in list(REGISTRY._collector_to_names.keys()):
        if c not in snapshot:
            REGISTRY.unregister(c)


class TestFullPluginRegistry:
    async def test_http_and_workers_present_with_log_provider(self) -> None:
        """
        Given SharedProvider + AdminMetricsProvider + AdminLogWebProvider,
        When the container resolves IModulePluginRegistry,
        Then only the metrics-owned 'http' and 'workers' plugins are present
        (the log subsystem no longer registers a metrics module).
        """
        container = make_async_container(
            SharedProvider(),
            AdminMetricsProvider(),
            AdminLogWebProvider(),
        )
        try:
            reg = await container.get(IModulePluginRegistry)
            slugs = sorted(p.slug for p in reg.all())
            assert slugs == ["http", "workers"]
        finally:
            await container.close()
