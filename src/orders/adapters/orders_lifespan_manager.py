from dataclasses import dataclass

import asyncpg

from .driven.migrations_runner import apply_migrations


@dataclass(slots=True, kw_only=True)
class OrdersLifespanManager:
    pool: asyncpg.Pool
    yoyo_url: str

    async def start(self) -> None:
        await apply_migrations(self.yoyo_url)

    async def stop(self) -> None:
        await self.pool.close()
