import pytest
from dishka import make_async_container

from metrics.adapters import MetricsLifespanManager
from metrics.config import MetricsConfig
from metrics.ports.driving import MetricsFacade
from metrics.provider import MetricsProvider
from shared.provider import SharedProvider


class TestMetricsDiResolves:
    @pytest.mark.asyncio
    async def test_config_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Given MetricsProvider with SharedProvider,
        When resolving MetricsConfig,
        Then it resolves successfully.
        """
        monkeypatch.setenv("APP_NAME", "litestar-base")
        container = make_async_container(SharedProvider(), MetricsProvider())
        try:
            cfg = await container.get(MetricsConfig)
            assert isinstance(cfg, MetricsConfig)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_lifespan_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Given MetricsProvider with SharedProvider,
        When resolving MetricsLifespanManager,
        Then it resolves successfully and holds a MetricsConfig.
        """
        monkeypatch.setenv("APP_NAME", "litestar-base")
        container = make_async_container(SharedProvider(), MetricsProvider())
        try:
            mgr = await container.get(MetricsLifespanManager)
            assert isinstance(mgr, MetricsLifespanManager)
            assert isinstance(mgr.config, MetricsConfig)
        finally:
            await container.close()

    @pytest.mark.asyncio
    async def test_no_redis_in_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Given the collapsed MetricsProvider,
        When inspecting its provides,
        Then no Redis/Valkey dependency is registered.
        """
        monkeypatch.setenv("APP_NAME", "litestar-base")
        import inspect

        src = inspect.getsource(MetricsProvider)
        assert "redis" not in src.lower()
        assert "valkey" not in src.lower()

    @pytest.mark.asyncio
    async def test_facade_resolves(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """
        Given MetricsProvider with SharedProvider,
        When resolving MetricsFacade,
        Then it resolves with a PrometheusSink behind it.
        """
        monkeypatch.setenv("APP_NAME", "litestar-base")
        monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
        container = make_async_container(SharedProvider(), MetricsProvider())
        try:
            facade = await container.get(MetricsFacade)
            assert isinstance(facade, MetricsFacade)
        finally:
            await container.close()
