import pytest
from dishka import make_async_container

from admin.metrics.config import MetricsConfig
from admin.metrics.provider import AdminMetricsProvider

pytestmark = pytest.mark.asyncio


class TestProviderWiring:
    async def test_config_resolvable(self) -> None:
        """
        Given a container built from AdminMetricsProvider,
        When resolving MetricsConfig,
        Then a default-constructed instance is returned.
        """
        container = make_async_container(AdminMetricsProvider())
        try:
            cfg = await container.get(MetricsConfig)
            assert isinstance(cfg, MetricsConfig)
        finally:
            await container.close()
