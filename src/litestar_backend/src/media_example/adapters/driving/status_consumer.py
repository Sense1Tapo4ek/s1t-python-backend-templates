import asyncio
import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import msgspec
import redis.asyncio as aioredis
import structlog
from prometheus_client import Counter
from redis.exceptions import ResponseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.generics.errors import AppError, DomainError

from ...ports.driving import MediaFacade, VideoStatusEventSchema

_log = structlog.get_logger("media_example.status_consumer")

VIDEO_STATUS_STREAM = "video_status"
CONSUMER_GROUP = "media_example"
_CONSUMER = f"{CONSUMER_GROUP}-{socket.gethostname()}"

STATUS_EVENTS_CONSUMED = Counter(
    "media_example_status_events_consumed_total",
    "video_status events consumed, by event type",
    ["event_type"],
)


@dataclass(slots=True, kw_only=True)
class VideoStatusConsumer:
    _valkey: aioredis.Redis
    _sessionmaker: async_sessionmaker[AsyncSession]
    _facade_factory: Callable[[AsyncSession], MediaFacade]
    _batch: int = 100
    _block_ms: int = 1000

    async def ensure_group(self) -> None:
        """Create the consumer group, tolerating BUSYGROUP if it already exists."""
        try:
            await self._valkey.xgroup_create(
                VIDEO_STATUS_STREAM, CONSUMER_GROUP, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def run_forever(self) -> None:
        """Main loop: ensure group then drain entries indefinitely."""
        await self.ensure_group()
        while True:
            try:
                await self.drain_once()
            except Exception:
                _log.exception("status consumer drain failed")
                await asyncio.sleep(1.0)

    async def drain_once(self) -> int:
        """Read up to _batch entries, apply each, ack on success/permanent failure.

        Returns the number of acked entries. Entries that trigger PortError or
        unknown exceptions are NOT acked and will be redelivered on restart.
        """
        resp: Any = await self._valkey.xreadgroup(
            CONSUMER_GROUP,
            _CONSUMER,
            {VIDEO_STATUS_STREAM: ">"},
            count=self._batch,
            block=self._block_ms,
        )
        handled = 0
        for _stream, entries in resp or []:
            for entry_id, fields in entries:
                if await self._handle(fields):
                    await self._valkey.xack(VIDEO_STATUS_STREAM, CONSUMER_GROUP, entry_id)
                    handled += 1
        return handled

    async def _handle(self, fields: dict[str, str]) -> bool:
        """Apply one event; return True to ack (applied or permanently unprocessable)."""
        try:
            event = msgspec.json.decode(fields["payload"], type=VideoStatusEventSchema)
        except (msgspec.MsgspecError, KeyError):
            _log.warning("video_status malformed payload dropped", raw=str(fields)[:200])
            return True

        try:
            async with self._sessionmaker() as session:
                facade = self._facade_factory(session)
                if event.event_type == "video_processing_started":
                    await facade.mark_processing(event.video_id)
                elif event.event_type == "video_processed":
                    await facade.mark_done(event.video_id)
                elif event.event_type == "video_processing_failed":
                    await facade.mark_failed(event.video_id)
                else:
                    _log.warning(
                        "video_status unknown event_type dropped",
                        event_type=event.event_type,
                    )
                    return True
        except (DomainError, AppError) as exc:
            # Duplicate delivery or unknown video: permanently inapplicable -- ack.
            _log.warning(
                "video_status event skipped",
                video_id=str(event.video_id),
                reason=str(exc),
            )
            return True

        STATUS_EVENTS_CONSUMED.labels(event_type=event.event_type).inc()
        _log.info(
            "video_status applied",
            video_id=str(event.video_id),
            event_type=event.event_type,
        )
        return True
