"""Assembles one per-worker snapshot and pushes it to the publisher.

Pure orchestration — no I/O of its own. Sampler signatures are intentional:
- loop_lag is read from a live rolling window (started elsewhere)
- rss is sampled on demand (cheap syscall)
- queue depth is optional; sink processes don't have a producer queue
"""

from dataclasses import dataclass
from datetime import datetime

from ...domain import WorkerIdVo
from ..interfaces import (
    ILoopLagSampler,
    IMetricsPublisher,
    IQueueDepthProvider,
    IRssSampler,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class PublishWorkerSnapshotUc:
    _publisher: IMetricsPublisher
    _loop_lag_sampler: ILoopLagSampler
    _rss_sampler: IRssSampler
    _queue_depth_provider: IQueueDepthProvider | None
    _worker_id: WorkerIdVo
    _role: str
    _started_at: datetime

    async def __call__(self) -> None:
        fields: dict[str, str] = {
            "started_at": self._started_at.isoformat(),
            "rss_bytes": str(self._rss_sampler.current_rss_bytes()),
            "loop_lag_p95_ms": f"{self._loop_lag_sampler.current_p95_ms():.2f}",
        }
        if self._queue_depth_provider is not None:
            fields["log_queue_depth"] = str(
                self._queue_depth_provider.current_queue_depth()
            )
            fields["log_dropped_total"] = str(
                self._queue_depth_provider.total_dropped()
            )
        await self._publisher.publish(
            worker_id=self._worker_id,
            role=self._role,
            fields=fields,
        )
