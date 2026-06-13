import asyncio
from dataclasses import dataclass

import redis.asyncio as aioredis
import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger("media_example.relay")
VIDEO_UPLOADED_STREAM = "video_uploaded"

# Unqualified table names resolve via the engine's search_path (set to the
# context schema in build_engine), so the relay follows MEDIA_SCHEMA_NAME.
_CLAIM = text(
    "SELECT id, event_type, payload FROM outbox_messages "
    "WHERE sent_at IS NULL ORDER BY created_at "
    "FOR UPDATE SKIP LOCKED LIMIT :batch"
)
_MARK = text("UPDATE outbox_messages SET sent_at = now() WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)


@dataclass(slots=True, kw_only=True)
class OutboxRelay:
    _sessionmaker: async_sessionmaker[AsyncSession]
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
        async with self._sessionmaker() as session, session.begin():
            rows = (await session.execute(_CLAIM, {"batch": self._batch})).mappings().all()
            if not rows:
                return 0
            for r in rows:
                await self._valkey.xadd(
                    VIDEO_UPLOADED_STREAM,
                    {
                        "event_id": str(r["id"]),
                        "event_type": r["event_type"],
                        "payload": r["payload"],
                    },
                )
            await session.execute(_MARK, {"ids": [r["id"] for r in rows]})
            _log.info("relay published", count=len(rows))
            return len(rows)
