import asyncio
from dataclasses import dataclass, field

import structlog

from shared.adapters.driven.outbox_relay import OutboxRelay
from shared.adapters.driven.postgres import run_migrations
from shared.generics.config import PROJECT_ROOT

_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "auth")
_log = structlog.get_logger("auth.lifespan")


@dataclass(slots=True, kw_only=True)
class AuthLifespanManager:
    yoyo_url: str
    relay: OutboxRelay
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)

    async def start(self) -> None:
        await run_migrations(self.yoyo_url, _MIGRATIONS_DIR)
        self._tasks = [asyncio.create_task(self.relay.run_forever())]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                _log.exception("auth task crashed during shutdown")
