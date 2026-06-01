import pytest
from dishka import make_async_container

from admin.metrics.config import MetricsConfig
from admin.metrics.provider import AdminMetricsProvider
from shared.config import BaseAppConfig
from shared.provider import SharedProvider

pytestmark = pytest.mark.asyncio


class TestProviderBoot:
    async def test_config_and_base_config_both_resolve(self) -> None:
        """
        Given AdminMetricsProvider co-existing with SharedProvider,
        When resolving MetricsConfig and BaseAppConfig,
        Then both come back successfully — no DI cycles.
        """
        container = make_async_container(
            SharedProvider(),
            AdminMetricsProvider(),
        )
        try:
            metrics_cfg = await container.get(MetricsConfig)
            base_cfg = await container.get(BaseAppConfig)
            assert metrics_cfg.enabled is True
            assert base_cfg.app_name
        finally:
            await container.close()
