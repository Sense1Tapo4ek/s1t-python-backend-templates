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

        uc = PublishWorkerSnapshotUc(
            _publisher=publisher,
            _loop_lag_sampler=loop_lag,
            _rss_sampler=rss,
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
        assert fields["started_at"].startswith("2026-05-12T12:00:00")
        assert "log_queue_depth" not in fields
        assert "log_dropped_total" not in fields
