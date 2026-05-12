import pytest
from dishka import make_async_container
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend
from prometheus_client import REGISTRY

from admin.log.provider import AdminLogPortBindings, AdminLogWebProvider
from admin.metrics.app.interfaces import IModulePluginRegistry
from admin.metrics.provider import AdminMetricsProvider
from shared.provider import SharedProvider

pytestmark = pytest.mark.asyncio


def _channels_plugin() -> ChannelsPlugin:
    return ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )


@pytest.fixture(autouse=True)
def _isolated_registry():
    snapshot = list(REGISTRY._collector_to_names.keys())
    yield
    for c in list(REGISTRY._collector_to_names.keys()):
        if c not in snapshot:
            REGISTRY.unregister(c)


class TestFullPluginRegistry:
    async def test_http_logs_workers_all_present(self) -> None:
        """
        Given SharedProvider + AdminMetricsProvider + AdminLogWebProvider + AdminLogPortBindings,
        When the container resolves IModulePluginRegistry,
        Then 'http', 'logs', and 'workers' plugins are all present.
        """
        container = make_async_container(
            SharedProvider(channels_plugin=_channels_plugin()),
            AdminMetricsProvider(),
            AdminLogWebProvider(),
            AdminLogPortBindings(),
        )
        try:
            reg = await container.get(IModulePluginRegistry)
            slugs = sorted(p.slug for p in reg.all())
            assert slugs == ["http", "logs", "workers"]
        finally:
            await container.close()
