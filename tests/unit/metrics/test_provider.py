import pytest
from dishka import make_async_container

from metrics.config import MetricsConfig
from metrics.provider import MetricsProvider
from shared.provider import SharedProvider

pytestmark = pytest.mark.asyncio


class TestProviderWiring:
    async def test_config_resolvable(self) -> None:
        """
        Given a container built from MetricsProvider + SharedProvider,
        When resolving MetricsConfig,
        Then a default-constructed instance is returned.
        """
        container = make_async_container(
            SharedProvider(),
            MetricsProvider(),
        )
        try:
            cfg = await container.get(MetricsConfig)
            assert isinstance(cfg, MetricsConfig)
        finally:
            await container.close()
