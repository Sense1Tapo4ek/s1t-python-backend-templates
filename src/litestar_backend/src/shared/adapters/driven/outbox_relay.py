import asyncio
from dataclasses import dataclass, field

import redis.asyncio as aioredis
import structlog
from sqlalchemy import TextClause, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger("shared.outbox_relay")

_TABLE = "outbox_messages"


@dataclass(slots=True, kw_only=True)
class OutboxRelay:
    """Drains a context's committed outbox rows into a Valkey stream.

    Generic over the target stream: each context provides its own sessionmaker
    (whose engine's search_path pins the context schema, so the unqualified
    table name resolves there) and the stream it publishes to. Claims rows
    FOR UPDATE SKIP LOCKED, so several relay instances are safe.
    """

    _sessionmaker: async_sessionmaker[AsyncSession]
    _valkey: aioredis.Redis
    _stream: str
    _batch: int = 100
    _idle_sleep: float = 0.5
    _claim: TextClause = field(init=False)
    _mark: TextClause = field(init=False)

    def __post_init__(self) -> None:
        self._claim = text(
            f"SELECT id, event_type, payload FROM {_TABLE} "
            "WHERE sent_at IS NULL ORDER BY created_at "
            "FOR UPDATE SKIP LOCKED LIMIT :batch"
        )
        self._mark = text(f"UPDATE {_TABLE} SET sent_at = now() WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )

    async def run_forever(self) -> None:
        while True:
            try:
                published = await self._drain_once()
            except Exception:
                _log.exception("relay drain failed", stream=self._stream)
                published = 0
            if published == 0:
                await asyncio.sleep(self._idle_sleep)

    async def _drain_once(self) -> int:
        async with self._sessionmaker() as session, session.begin():
            rows = (await session.execute(self._claim, {"batch": self._batch})).mappings().all()
            if not rows:
                return 0
            for r in rows:
                await self._valkey.xadd(
                    self._stream,
                    {
                        "event_id": str(r["id"]),
                        "event_type": r["event_type"],
                        "payload": r["payload"],
                    },
                )
            await session.execute(self._mark, {"ids": [r["id"] for r in rows]})
            _log.info("relay published", stream=self._stream, count=len(rows))
            return len(rows)
