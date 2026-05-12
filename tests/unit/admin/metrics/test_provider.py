import pytest
from dishka import make_async_container
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

from admin.metrics.config import MetricsConfig
from admin.metrics.provider import AdminMetricsProvider
from shared.provider import SharedProvider

pytestmark = pytest.mark.asyncio


def _channels_plugin() -> ChannelsPlugin:
    return ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )


class TestProviderWiring:
    async def test_config_resolvable(self) -> None:
        """
        Given a container built from AdminMetricsProvider + SharedProvider,
        When resolving MetricsConfig,
        Then a default-constructed instance is returned.
        """
        container = make_async_container(
            SharedProvider(channels_plugin=_channels_plugin()),
            AdminMetricsProvider(),
        )
        try:
            cfg = await container.get(MetricsConfig)
            assert isinstance(cfg, MetricsConfig)
        finally:
            await container.close()
