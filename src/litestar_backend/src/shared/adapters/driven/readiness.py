import asyncio
from dataclasses import dataclass

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadinessReport:
    ok: bool
    checks: dict[str, str]


@dataclass(slots=True, kw_only=True)
class ReadinessProbe:
    """Pings the hard runtime dependencies for the readiness endpoint.

    A probe, not a gate: every failure is caught and reported as "down" in the
    `checks` map rather than raised, so one unreachable dependency never masks
    another. The driving adapter maps the report to an HTTP status.
    """

    _engine: AsyncEngine
    _valkey: aioredis.Redis
    _timeout_s: float = 2.0

    async def check(self) -> ReadinessReport:
        checks = {
            "postgres": await self._probe_postgres(),
            "valkey": await self._probe_valkey(),
        }
        return ReadinessReport(ok=all(v == "up" for v in checks.values()), checks=checks)

    async def _probe_postgres(self) -> str:
        try:
            async with self._engine.connect() as conn:
                await asyncio.wait_for(conn.execute(text("SELECT 1")), self._timeout_s)
        except Exception:  # a probe degrades to "down" on any failure
            return "down"
        return "up"

    async def _probe_valkey(self) -> str:
        try:
            await asyncio.wait_for(self._valkey.ping(), self._timeout_s)
        except Exception:  # a probe degrades to "down" on any failure
            return "down"
        return "up"
