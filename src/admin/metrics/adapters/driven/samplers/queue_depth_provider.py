"""Reads producer-queue depth from RedisStreamPublisher.

The publisher exposes its asyncio.Queue via `.buffer`. The drop counter
lives on `shared.logging._QueueLogger` as a class-level field — it
aggregates drops across all loggers in this process. Reading those is
cheap; both are pull-based and called from PublishWorkerSnapshotUc.
"""

from dataclasses import dataclass

from admin.log.ports.driven.gateways import RedisStreamPublisher
from shared.logging import _QueueLogger


@dataclass(slots=True, kw_only=True)
class RedisStreamQueueDepthProvider:
    _publisher: RedisStreamPublisher

    def current_queue_depth(self) -> int:
        return self._publisher.buffer.qsize()

    def total_dropped(self) -> int:
        return int(_QueueLogger._dropped_total)
