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


@dataclass(slots=True, kw_only=True, eq=False)
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

    def describe(self) -> Iterable[Metric]:
        """Return metric descriptors without data — used by REGISTRY.register().

        Providing `describe()` lets prometheus_client skip calling `collect()`
        during registration, avoiding a deadlock when `register()` is called
        from inside a running event loop (lifespan startup).
        """
        return [
            GaugeMetricFamily(
                f"{_METRIC_PREFIX}_worker_rss_bytes",
                "Resident memory of each worker, sampled by the worker itself.",
                labels=["role", "worker_id"],
            ),
            GaugeMetricFamily(
                f"{_METRIC_PREFIX}_worker_loop_lag_p95_ms",
                "Event loop lag, p95 over the last sampling window.",
                labels=["role", "worker_id"],
            ),
            GaugeMetricFamily(
                f"{_METRIC_PREFIX}_worker_alive",
                "1 if the worker reported within TTL; aggregated by role at scrape.",
                labels=["role", "worker_id"],
            ),
        ]

    def collect(self) -> Iterable[Metric]:
        """Prometheus client entry point — sync.

        prometheus_client calls this from within an async request handler via
        `generate_latest()`. Submitting back to the running event loop deadlocks
        because the loop is blocked waiting on `future.result()`. Instead we
        run the coroutine in a fresh loop on a worker thread.
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: asyncio.run(self.acollect()))
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
