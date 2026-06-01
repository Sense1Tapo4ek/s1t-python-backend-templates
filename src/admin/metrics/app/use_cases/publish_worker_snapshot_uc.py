from dataclasses import dataclass
from datetime import datetime

from ...domain import WorkerIdVo
from ..interfaces import ILoopLagSampler, IMetricsPublisher, IRssSampler


@dataclass(frozen=True, slots=True, kw_only=True)
class PublishWorkerSnapshotUc:
    _publisher: IMetricsPublisher
    _loop_lag_sampler: ILoopLagSampler
    _rss_sampler: IRssSampler
    _worker_id: WorkerIdVo
    _role: str
    _started_at: datetime

    async def __call__(self) -> None:
        fields: dict[str, str] = {
            "started_at": self._started_at.isoformat(),
            "rss_bytes": str(self._rss_sampler.current_rss_bytes()),
            "loop_lag_p95_ms": f"{self._loop_lag_sampler.current_p95_ms():.2f}",
        }
        await self._publisher.publish(
            worker_id=self._worker_id,
            role=self._role,
            fields=fields,
        )
