from datetime import UTC, datetime
from unittest.mock import AsyncMock, create_autospec

import pytest

from admin.metrics.app.interfaces import (
    ILoopLagSampler,
    IMetricsPublisher,
    IRssSampler,
)
from admin.metrics.app.use_cases import PublishWorkerSnapshotUc
from admin.metrics.domain import WorkerIdVo


class TestPublishWorkerSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_has_no_log_queue_fields(self) -> None:
        """
        Given the decoupled metrics UC,
        When publishing a snapshot,
        Then no log_queue_depth / log_dropped_total fields are emitted.
        """
        # Arrange
        publisher = create_autospec(IMetricsPublisher, instance=True)
        publisher.publish = AsyncMock()
        loop_lag = create_autospec(ILoopLagSampler, instance=True)
        loop_lag.current_p95_ms.return_value = 1.0
        rss = create_autospec(IRssSampler, instance=True)
        rss.current_rss_bytes.return_value = 100
        uc = PublishWorkerSnapshotUc(
            _publisher=publisher,
            _loop_lag_sampler=loop_lag,
            _rss_sampler=rss,
            _worker_id=WorkerIdVo(host="h", pid=1),
            _role="api",
            _started_at=datetime.now(UTC),
        )

        # Act
        await uc()

        # Assert
        fields = publisher.publish.call_args.kwargs["fields"]
        assert "log_queue_depth" not in fields
        assert "log_dropped_total" not in fields

    def test_queue_depth_interface_gone(self) -> None:
        """
        Given the decoupling,
        When importing IQueueDepthProvider,
        Then ImportError.
        """
        with pytest.raises(ImportError):
            from admin.metrics.app.interfaces import (  # noqa: F401
                IQueueDepthProvider,
            )
