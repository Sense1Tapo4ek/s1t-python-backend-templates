from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import msgspec
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.generics.errors import PortError

from ...adapters.driven.metrics import STATUS_EVENTS_PUBLISHED
from ...app import IEventPublisher
from .integration_events import VideoStatusIntegration

VIDEO_STATUS_STREAM = "video_status"


@dataclass(slots=True, kw_only=True)
class ValkeyEventPublisher(IEventPublisher):
    _valkey: aioredis.Redis

    async def publish_started(self, video_id: UUID) -> None:
        await self._publish(video_id, "video_processing_started")

    async def publish_processed(self, video_id: UUID) -> None:
        await self._publish(video_id, "video_processed")

    async def publish_failed(self, video_id: UUID) -> None:
        await self._publish(video_id, "video_processing_failed")

    async def _publish(self, video_id: UUID, event_type: str) -> None:
        event = VideoStatusIntegration(
            event_id=uuid4(),
            event_type=event_type,
            video_id=video_id,
            occurred_at=datetime.now(UTC),
        )
        try:
            await self._valkey.xadd(
                VIDEO_STATUS_STREAM,
                {
                    "event_id": str(event.event_id),
                    "event_type": event.event_type,
                    "payload": msgspec.json.encode(event).decode(),
                },
            )
        except RedisError as exc:
            raise PortError(f"video_status publish failed for {video_id}: {exc}") from exc
        STATUS_EVENTS_PUBLISHED.labels(event_type=event.event_type).inc()
