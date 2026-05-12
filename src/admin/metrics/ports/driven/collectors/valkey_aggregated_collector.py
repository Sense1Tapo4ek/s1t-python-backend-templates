"""Aggregates per-worker metrics from Valkey hashes for /metrics scrapes.

Runs on every Prometheus scrape. Must be cheap (SCAN + HGETALL x
small N) and must not raise — a scrape failure would surface as a
Prometheus alert that masks the underlying outage.

Sync `collect()` is the protocol Prometheus client expects. Internally
we await `acollect()` on the current event loop via asyncio.run_coroutine
when called from a sync context. The recommended integration point is
via `Collector` registered on `REGISTRY` — see provider.py.
"""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

import structlog
from prometheus_client.metrics_core import GaugeMetricFamily, Metric

_log = structlog.get_logger(__name__)


class IRedisClient(Protocol):
    def scan_iter(self, match: str, count: int = 100) -> Any: ...

    async def hgetall(self, key: Any) -> Any: ...


_METRIC_PREFIX = "admin_metrics"


@dataclass(slots=True, kw_only=True)
class ValkeyAggregatedCollector:
    _redis: IRedisClient
    _key_prefix: str

    async def acollect(self) -> Iterable[Metric]:
        rss = GaugeMetricFamily(
            f"{_METRIC_PREFIX}_worker_rss_bytes",
            "Resident memory of each worker, sampled by the worker itself.",
            labels=["role", "worker_id"],
        )
        lag = GaugeMetricFamily(
            f"{_METRIC_PREFIX}_worker_loop_lag_p95_ms",
            "Event loop lag, p95 over the last sampling window.",
            labels=["role", "worker_id"],
        )
        alive = GaugeMetricFamily(
            f"{_METRIC_PREFIX}_worker_alive",
            "1 if the worker reported within TTL; aggregated by role at scrape.",
            labels=["role", "worker_id"],
        )

        try:
            async for key in self._redis.scan_iter(
                match=f"{self._key_prefix}*", count=200
            ):
                raw = await self._redis.hgetall(key)
                if not raw:
                    continue
                fields = {_decode(k): _decode(v) for k, v in raw.items()}
                role = fields.get("role", "")
                worker_id = fields.get("worker_id", "")
                if not role or not worker_id:
                    continue
                alive.add_metric([role, worker_id], 1.0)
                if (val := _parse_float(fields.get("rss_bytes"))) is not None:
                    rss.add_metric([role, worker_id], val)
                if (val := _parse_float(fields.get("loop_lag_p95_ms"))) is not None:
                    lag.add_metric([role, worker_id], val)
        except Exception as exc:
            _log.warning(
                "metrics collector scan failed",
                error_type=type(exc).__name__,
            )
            return ()

        return (alive, rss, lag)

    def collect(self) -> Iterable[Metric]:
        """Prometheus client entry point — sync."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return list(asyncio.run(self.acollect()))
        future = asyncio.run_coroutine_threadsafe(self.acollect(), loop)
        return list(future.result(timeout=10.0))


def _decode(v: Any) -> str:
    if isinstance(v, bytes):
        return v.decode()
    return str(v)


def _parse_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None
