import pytest
from dishka import make_async_container
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend

from admin.metrics.config import MetricsConfig
from admin.metrics.provider import AdminMetricsProvider
from shared.config import BaseAppConfig
from shared.provider import SharedProvider

pytestmark = pytest.mark.asyncio


def _channels_plugin() -> ChannelsPlugin:
    return ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )


class TestProviderBoot:
    async def test_config_and_base_config_both_resolve(self) -> None:
        """
        Given AdminMetricsProvider co-existing with SharedProvider,
        When resolving MetricsConfig and BaseAppConfig,
        Then both come back successfully — no DI cycles.
        """
        container = make_async_container(
            SharedProvider(channels_plugin=_channels_plugin()),
            AdminMetricsProvider(),
        )
        try:
            metrics_cfg = await container.get(MetricsConfig)
            base_cfg = await container.get(BaseAppConfig)
            assert metrics_cfg.enabled is True
            assert base_cfg.app_name
        finally:
            await container.close()
