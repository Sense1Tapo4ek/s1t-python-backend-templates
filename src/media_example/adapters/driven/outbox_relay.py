import asyncio
from dataclasses import dataclass

import asyncpg
import redis.asyncio as aioredis
import structlog

_log = structlog.get_logger("media_example.relay")
VIDEO_UPLOADED_STREAM = "video_uploaded"

_CLAIM = """
SELECT id, event_type, payload FROM media.outbox_messages
WHERE sent_at IS NULL ORDER BY created_at
FOR UPDATE SKIP LOCKED LIMIT $1
"""
_MARK = "UPDATE media.outbox_messages SET sent_at = now() WHERE id = ANY($1::uuid[])"


@dataclass(slots=True, kw_only=True)
class OutboxRelay:
    _pool: asyncpg.Pool
    _valkey: aioredis.Redis
    _batch: int = 100
    _idle_sleep: float = 0.5

    async def run_forever(self) -> None:
        while True:
            try:
                published = await self._drain_once()
            except Exception:
                _log.exception("relay drain failed")
                published = 0
            if published == 0:
                await asyncio.sleep(self._idle_sleep)

    async def _drain_once(self) -> int:
        async with self._pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(_CLAIM, self._batch)
            if not rows:
                return 0
            for r in rows:
                await self._valkey.xadd(
                    VIDEO_UPLOADED_STREAM,
                    {"event_id": str(r["id"]), "event_type": r["event_type"], "payload": r["payload"]},
                )
            await conn.execute(_MARK, [r["id"] for r in rows])
            _log.info("relay published", count=len(rows))
            return len(rows)
