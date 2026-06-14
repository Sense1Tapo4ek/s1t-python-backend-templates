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
        # Probe dependencies concurrently so total latency is ~_timeout_s, not
        # the sum -- a single hung dependency must not blow the readiness budget.
        postgres, valkey = await asyncio.gather(self._probe_postgres(), self._probe_valkey())
        checks = {"postgres": postgres, "valkey": valkey}
        return ReadinessReport(ok=all(v == "up" for v in checks.values()), checks=checks)

    async def _probe_postgres(self) -> str:
        # Bound the WHOLE probe (connect handshake + query): a host that accepts
        # TCP but stalls on the wire protocol must still degrade to "down" within
        # the budget, not block on asyncpg's default 60s connect timeout.
        try:
            async with asyncio.timeout(self._timeout_s):
                async with self._engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
        except Exception:
            return "down"
        return "up"

    async def _probe_valkey(self) -> str:
        try:
            async with asyncio.timeout(self._timeout_s):
                await self._valkey.ping()
        except Exception:
            return "down"
        return "up"
