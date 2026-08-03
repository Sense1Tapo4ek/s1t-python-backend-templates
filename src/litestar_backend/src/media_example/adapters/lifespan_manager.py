import asyncio
from dataclasses import dataclass, field

import structlog

from shared.adapters.driven.idempotency_sweeper import IdempotencySweeper
from shared.adapters.driven.outbox_relay import OutboxRelay
from shared.adapters.driven.postgres import run_migrations
from shared.generics.config import PROJECT_ROOT

from .driving.status_consumer import VideoStatusConsumer

_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "media")
_log = structlog.get_logger("media_example.lifespan")


@dataclass(slots=True, kw_only=True)
class MediaLifespanManager:
    yoyo_url: str
    relay: OutboxRelay
    consumer: VideoStatusConsumer
    sweeper: IdempotencySweeper
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)

    async def start(self) -> None:
        await run_migrations(self.yoyo_url, _MIGRATIONS_DIR)
        self._tasks = [
            asyncio.create_task(self.relay.run_forever()),
            asyncio.create_task(self.consumer.run_forever()),
            asyncio.create_task(self.sweeper.run_forever()),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        # Join every task even if an earlier one stored a crash -- an early
        # propagate would leave the later task cancelled but never awaited.
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                _log.exception("media task crashed during shutdown")
