import pytest
from dishka import Provider, Scope, make_async_container, provide

from admin.metrics.app.use_cases import PublishWorkerSnapshotUc
from admin.metrics.provider import AdminMetricsProvider
from shared.config import BaseAppConfig


class _BaseConfigProvider(Provider):
    scope = Scope.APP

    @provide
    def base_config(self) -> BaseAppConfig:
        return BaseAppConfig()


class TestMetricsDi:
    @pytest.mark.asyncio
    async def test_publish_uc_resolves_without_queue_provider(
        self, monkeypatch
    ) -> None:
        """
        Given the decoupled metrics provider,
        When resolving PublishWorkerSnapshotUc from the container,
        Then it builds without any log-supplied IQueueDepthProvider.
        """
        # Arrange
        monkeypatch.setenv("APP_NAME", "litestar-base")
        monkeypatch.setenv("VALKEY_URL", "redis://localhost:6379/0")
        container = make_async_container(
            _BaseConfigProvider(), AdminMetricsProvider()
        )

        # Act
        uc = await container.get(PublishWorkerSnapshotUc)

        # Assert
        assert isinstance(uc, PublishWorkerSnapshotUc)
        await container.close()
