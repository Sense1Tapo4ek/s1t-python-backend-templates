from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from admin.metrics.app.use_cases import PublishWorkerSnapshotUc
from admin.metrics.domain import WorkerIdVo

pytestmark = pytest.mark.asyncio


class TestPublishWorkerSnapshotUc:
    async def test_collects_and_publishes(self) -> None:
        """
        Given samplers and a publisher,
        When the UC runs,
        Then publisher.publish is called once with the merged fields.
        """
        publisher = AsyncMock()
        loop_lag = MagicMock()
        loop_lag.current_p95_ms.return_value = 3.2
        rss = MagicMock()
        rss.current_rss_bytes.return_value = 192_512_000
        qdepth = MagicMock()
        qdepth.current_queue_depth.return_value = 12
        qdepth.total_dropped.return_value = 0

        uc = PublishWorkerSnapshotUc(
            _publisher=publisher,
            _loop_lag_sampler=loop_lag,
            _rss_sampler=rss,
            _queue_depth_provider=qdepth,
            _worker_id=WorkerIdVo(host="h", pid=1),
            _role="api",
            _started_at=datetime(2026, 5, 12, 12, tzinfo=UTC),
        )

        await uc()

        publisher.publish.assert_awaited_once()
        (call_args,) = publisher.publish.call_args_list
        kw = call_args.kwargs
        assert kw["role"] == "api"
        assert kw["worker_id"] == WorkerIdVo(host="h", pid=1)
        fields = kw["fields"]
        assert fields["rss_bytes"] == "192512000"
        assert fields["loop_lag_p95_ms"].startswith("3.2")
        assert fields["log_queue_depth"] == "12"
        assert fields["log_dropped_total"] == "0"
        assert fields["started_at"].startswith("2026-05-12T12:00:00")

    async def test_no_queue_depth_provider_is_ok(self) -> None:
        """
        Given no IQueueDepthProvider (sink process),
        When the UC runs,
        Then fields omit log_queue_depth without raising.
        """
        publisher = AsyncMock()
        loop_lag = MagicMock()
        loop_lag.current_p95_ms.return_value = 1.0
        rss = MagicMock()
        rss.current_rss_bytes.return_value = 1

        uc = PublishWorkerSnapshotUc(
            _publisher=publisher,
            _loop_lag_sampler=loop_lag,
            _rss_sampler=rss,
            _queue_depth_provider=None,
            _worker_id=WorkerIdVo(host="h", pid=1),
            _role="sink",
            _started_at=datetime(2026, 5, 12, 12, tzinfo=UTC),
        )
        await uc()
        fields = publisher.publish.call_args.kwargs["fields"]
        assert "log_queue_depth" not in fields
