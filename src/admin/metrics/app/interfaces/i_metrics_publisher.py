from typing import Protocol

from ...domain import WorkerIdVo


class IMetricsPublisher(Protocol):
    async def publish(
        self,
        worker_id: WorkerIdVo,
        role: str,
        fields: dict[str, str],
    ) -> None: ...
