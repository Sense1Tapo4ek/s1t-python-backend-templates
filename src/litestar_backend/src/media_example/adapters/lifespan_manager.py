import asyncio
import contextlib
from dataclasses import dataclass, field

from shared.adapters.driven.postgres import run_migrations
from shared.generics.config import PROJECT_ROOT

from .driven.outbox_relay import OutboxRelay

_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "media")


@dataclass(slots=True, kw_only=True)
class MediaLifespanManager:
    yoyo_url: str
    relay: OutboxRelay
    _task: asyncio.Task[None] | None = field(default=None)

    async def start(self) -> None:
        await run_migrations(self.yoyo_url, _MIGRATIONS_DIR)
        self._task = asyncio.create_task(self.relay.run_forever())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
