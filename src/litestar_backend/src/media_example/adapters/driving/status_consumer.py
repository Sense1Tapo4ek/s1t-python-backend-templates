import asyncio
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import msgspec
import redis.asyncio as aioredis
from prometheus_client import Counter
from redis.exceptions import ResponseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.generics.errors import AppError, DomainError, PortError
from shared.logging import Layer, layer_logger

from ...ports.driving import MediaFacade, VideoStatusEventSchema

_log = layer_logger(Layer.ADAPTERS_DRIVING, "media_example.status_consumer")

VIDEO_STATUS_STREAM = "video_status"
CONSUMER_GROUP = "media_example"
_CONSUMER = f"{CONSUMER_GROUP}-{socket.gethostname()}-{os.getpid()}"

STATUS_EVENTS_CONSUMED = Counter(
    "media_example_status_events_consumed_total",
    "video_status events consumed, by event type",
    ["event_type"],
)


@dataclass(slots=True, kw_only=True)
class VideoStatusConsumer:
    """Consumer group reader for the video_status Valkey stream.

    Delivery semantics:
    - DomainError / AppError (duplicate, unknown video): ack immediately
      (permanently inapplicable).
    - PortError or any unexpected exception: NOT acked; the entry stays in the
      consumer's PEL as pending.
    - Pending entries idle longer than _claim_idle_ms are adopted by any live
      consumer via XAUTOCLAIM on the next cycle (at-least-once delivery).
    - Consumer name is unique per process (_CONSUMER = group-host-pid), so a dead
      worker's PEL entries are unclaimed and available for recovery by its
      replacement or any live sibling.

    Prerequisite: ensure_group() must be called before drain_once(); run_forever()
    calls it automatically.
    """

    _valkey: aioredis.Redis
    _sessionmaker: async_sessionmaker[AsyncSession]
    _facade_factory: Callable[[AsyncSession], MediaFacade]
    _batch: int = 100
    _block_ms: int = 1000
    _claim_idle_ms: int = 60_000

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
        await self.ensure_group()
        while True:
            try:
                await self.drain_once()
            except Exception:
                _log.exception("status consumer drain failed")
                await asyncio.sleep(1.0)

    async def drain_once(self) -> int:
        """Read up to _batch entries, apply each, ack on success or permanent failure.

        Returns the number of acked entries.

        Semantics:
        - Entries that decode or apply cleanly are acked.
        - DomainError / AppError (duplicate delivery, unknown video): acked
          immediately as permanently inapplicable.
        - PortError or unknown exceptions: NOT acked; the entry stays pending
          in this consumer's PEL.
        - On the next cycle, _claim_stale() adopts pending entries idle past
          _claim_idle_ms (from this or any other consumer), providing
          at-least-once delivery across restarts and worker replacement.

        Prerequisite: ensure_group() must have been called beforehand
        (run_forever() does this automatically); calling drain_once() without
        a prior ensure_group() will raise ResponseError NOGROUP from Valkey.
        """
        handled = await self._claim_stale()
        resp: Any = await self._valkey.xreadgroup(
            CONSUMER_GROUP,
            _CONSUMER,
            {VIDEO_STATUS_STREAM: ">"},
            count=self._batch,
            block=self._block_ms,
        )
        handled += await self._apply_entries(resp or [])
        return handled

    async def _claim_stale(self) -> int:
        """Adopt pending entries idle past the threshold (crashed/replaced consumers).

        XAUTOCLAIM atomically reassigns them to this consumer; combined with the
        per-process consumer name this is what makes delivery at-least-once
        across restarts and worker replacement.

        If the stream or consumer group was deleted externally (NOGROUP error),
        the group is recreated so the next drain_once can proceed normally.

        Returns the number of successfully handled (and acked) claimed entries.
        """
        try:
            result: list[Any] = await self._valkey.xautoclaim(
                VIDEO_STATUS_STREAM,
                CONSUMER_GROUP,
                _CONSUMER,
                min_idle_time=self._claim_idle_ms,
                start_id="0-0",
                count=self._batch,
            )
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                _log.warning("video_status consumer group missing; recreating", error=str(exc))
                await self.ensure_group()
                return 0
            raise
        # redis-py 8.x parse_xautoclaim always returns a 3-element list:
        # [next_start_id, [(id, fields), ...], [deleted_ids]]
        _next, entries, _deleted = result
        if not entries:
            return 0
        return await self._apply_entries([(VIDEO_STATUS_STREAM, entries)])

    async def _apply_entries(self, streams: list[Any]) -> int:
        handled = 0
        for _stream, entries in streams:
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
        except PortError:
            # Transient infrastructure failure -- do NOT ack; entry stays pending.
            _log.warning(
                "video_status entry left pending (transient failure)",
                video_id=str(event.video_id),
            )
            raise

        STATUS_EVENTS_CONSUMED.labels(event_type=event.event_type).inc()
        _log.info(
            "video_status applied",
            video_id=str(event.video_id),
            event_type=event.event_type,
        )
        return True
