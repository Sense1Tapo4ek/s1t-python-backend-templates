import asyncio
from dataclasses import dataclass, field

import structlog
from sqlalchemy import TextClause, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger("shared.idempotency_sweeper")

_TABLE = "idempotency_keys"


@dataclass(slots=True, kw_only=True)
class IdempotencySweeper:
    """Deletes a context's idempotency keys past their retention horizon.

    Generic over the owning context the same way OutboxRelay is: the context
    supplies a sessionmaker whose engine pins its schema on the search_path, so
    the unqualified table name resolves there. Without this task the table only
    grows -- every retried write claims a key and nothing else removes it.

    Sweeps on a fixed interval rather than on the request path so a purge never
    delays a client, and swallows its own failures: a missed sweep costs disk,
    a crashed task would cost the loop.
    """

    _sessionmaker: async_sessionmaker[AsyncSession]
    _interval_seconds: float = 3600.0
    _purge: TextClause = field(init=False)

    def __post_init__(self) -> None:
        self._purge = text(f"DELETE FROM {_TABLE} WHERE expires_at < now()")

    async def run_forever(self) -> None:
        while True:
            await asyncio.sleep(self._interval_seconds)
            try:
                await self.purge_once()
            except Exception:
                _log.exception("idempotency purge failed", table=_TABLE)

    async def purge_once(self) -> int:
        async with self._sessionmaker() as session, session.begin():
            cursor: CursorResult = await session.execute(self._purge)  # type: ignore[assignment]
            purged = cursor.rowcount
        if purged:
            _log.info("idempotency keys purged", table=_TABLE, count=purged)
        return purged
