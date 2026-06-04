import asyncio
import contextlib
from dataclasses import dataclass, field

import asyncpg

from .driven.migrations_runner import apply_migrations
from .driven.outbox_relay import OutboxRelay


@dataclass(slots=True, kw_only=True)
class MediaLifespanManager:
    pool: asyncpg.Pool
    yoyo_url: str
    relay: OutboxRelay
    _task: asyncio.Task[None] | None = field(default=None)

    async def start(self) -> None:
        await apply_migrations(self.yoyo_url)
        self._task = asyncio.create_task(self.relay.run_forever())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self.pool.close()
