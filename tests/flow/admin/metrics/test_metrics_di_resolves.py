import pytest
from dishka import make_async_container

from admin.metrics.adapters.lifespan import MetricsLifespanManager
from admin.metrics.config import MetricsConfig
from admin.metrics.provider import AdminMetricsProvider
from shared.provider import SharedProvider


class TestMetricsDiResolves:
    @pytest.mark.asyncio
    async def test_config_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Given AdminMetricsProvider with SharedProvider,
        When resolving MetricsConfig,
        Then it resolves successfully.
        """
        monkeypatch.setenv("APP_NAME", "litestar-base")
        container = make_async_container(SharedProvider(), AdminMetricsProvider())
        try:
            cfg = await container.get(MetricsConfig)
            assert isinstance(cfg, MetricsConfig)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_lifespan_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Given AdminMetricsProvider with SharedProvider,
        When resolving MetricsLifespanManager,
        Then it resolves successfully and holds a MetricsConfig.
        """
        monkeypatch.setenv("APP_NAME", "litestar-base")
        container = make_async_container(SharedProvider(), AdminMetricsProvider())
        try:
            mgr = await container.get(MetricsLifespanManager)
            assert isinstance(mgr, MetricsLifespanManager)
            assert isinstance(mgr.config, MetricsConfig)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_no_redis_in_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Given the collapsed AdminMetricsProvider,
        When inspecting its provides,
        Then no Redis/Valkey dependency is registered.
        """
        monkeypatch.setenv("APP_NAME", "litestar-base")
        import inspect

        src = inspect.getsource(AdminMetricsProvider)
        assert "redis" not in src.lower()
        assert "valkey" not in src.lower()
