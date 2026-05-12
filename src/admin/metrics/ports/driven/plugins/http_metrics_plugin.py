"""HTTP module — RED metrics derived from prometheus_client.REGISTRY.

V1 scope: KPI strip pulls totals from REGISTRY (this process only) and
exposes them with NEUTRAL severity if zero. Per-route table is left as
a follow-up — cross-worker aggregation requires publishing route-level
breakdowns into Valkey, which we want to design carefully (cardinality).

The plugin maintains an internal ring buffer of (timestamp, total_count)
samples to derive 1m and 5m rates. The buffer is appended on every
summary() call — we accept that 5m-window precision is bound to UI
poll cadence (5s default; 60 samples = 5min).

`observe_for_test` is intentionally exposed so flow tests can drive
the plugin without booting Litestar middleware.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from html import escape as html_escape

from prometheus_client import Counter, Histogram

from ....domain import (
    DetailSectionVo,
    MetricKvVo,
    ModuleDetailVo,
    ModuleSummaryVo,
    Severity,
    classify,
)


_P95_WARN_MS = 200.0
_P95_BAD_MS = 500.0
_ERRORS_WARN = 1.0
_ERRORS_BAD = 11.0


@dataclass(slots=True, kw_only=True)
class HttpMetricsPlugin:
    _prefix: str
    name: str = "HTTP"
    slug: str = "http"
    description: str = "requests - latency - errors"
    _ring_size: int = 60
    _ring: deque[tuple[float, float, float]] = field(init=False)
    _requests_total: Counter = field(init=False)
    _request_duration: Histogram = field(init=False)
    _errors_total: Counter = field(init=False)

    def __post_init__(self) -> None:
        self._ring = deque(maxlen=self._ring_size)
        self._requests_total = Counter(
            f"{self._prefix}_requests_total",
            "Total HTTP requests observed by this plugin.",
            labelnames=("status",),
        )
        self._request_duration = Histogram(
            f"{self._prefix}_request_duration_seconds",
            "HTTP request duration in seconds.",
        )
        self._errors_total = Counter(
            f"{self._prefix}_errors_total",
            "Total HTTP responses with status_code >= 500.",
        )

    def observe_for_test(self, *, status: str, duration_s: float) -> None:
        self._requests_total.labels(status=status).inc()
        self._request_duration.observe(duration_s)
        if status.startswith("5"):
            self._errors_total.inc()

    async def summary(self) -> ModuleSummaryVo:
        now = time.monotonic()
        total_requests = sum(
            s.value for s in self._requests_total.collect()[0].samples
            if s.name.endswith("_total")
        )
        total_errors = sum(
            s.value for s in self._errors_total.collect()[0].samples
            if s.name.endswith("_total")
        )
        self._ring.append((now, total_requests, total_errors))

        rps_1m = self._rate(now, window_s=60.0, idx=1)
        err_5m = self._delta(now, window_s=300.0, idx=2)
        p95_5m_ms = _approx_p95_ms(self._request_duration)

        return ModuleSummaryVo(
            slug=self.slug, name=self.name,
            kvs=(
                MetricKvVo(
                    label="rps - 1m", value=f"{rps_1m:.1f} /s",
                    severity=Severity.NEUTRAL,
                ),
                MetricKvVo(
                    label="p95 - 5m", value=f"{p95_5m_ms:.0f} ms",
                    severity=classify(p95_5m_ms, warn=_P95_WARN_MS, bad=_P95_BAD_MS),
                ),
                MetricKvVo(
                    label="5xx - 5m", value=f"{int(err_5m)}",
                    severity=classify(err_5m, warn=_ERRORS_WARN, bad=_ERRORS_BAD),
                ),
            ),
        )

    async def detail(self) -> ModuleDetailVo:
        s = await self.summary()
        return ModuleDetailVo(
            slug=self.slug, name=self.name,
            sections=(
                DetailSectionVo(
                    title="KPI",
                    payload={"kvs": [(kv.label, kv.value) for kv in s.kvs]},
                ),
                DetailSectionVo(
                    title="By route (this worker)",
                    payload={
                        "note": (
                            "v1 shows per-process counts. Cross-worker "
                            "aggregation is a follow-up."
                        ),
                    },
                ),
            ),
        )

    def render_detail_html(self, detail: ModuleDetailVo) -> str:
        kpi = detail.sections[0].payload.get("kvs", []) if detail.sections else []
        kpi_html = "".join(
            f"<div class='metric'><span class='label'>{html_escape(l)}</span>"
            f"<span class='value'>{html_escape(v)}</span></div>"
            for (l, v) in kpi
        )
        note = (
            detail.sections[1].payload.get("note", "")
            if len(detail.sections) > 1 else ""
        )
        return (
            "<section class='panel'><h2>KPI</h2>"
            f"{kpi_html}"
            "</section>"
            "<section class='panel'><h2>By route</h2>"
            f"<p>{html_escape(note)}</p>"
            "</section>"
        )

    def _rate(self, now: float, *, window_s: float, idx: int) -> float:
        if len(self._ring) < 2:
            return 0.0
        latest = self._ring[-1]
        oldest = next(
            (s for s in self._ring if now - s[0] <= window_s), self._ring[0]
        )
        elapsed = latest[0] - oldest[0]
        if elapsed <= 0:
            return 0.0
        return (latest[idx] - oldest[idx]) / elapsed

    def _delta(self, now: float, *, window_s: float, idx: int) -> float:
        if len(self._ring) < 2:
            return 0.0
        latest = self._ring[-1]
        oldest = next(
            (s for s in self._ring if now - s[0] <= window_s), self._ring[0]
        )
        return max(0.0, latest[idx] - oldest[idx])


def _approx_p95_ms(hist: Histogram) -> float:
    samples = hist.collect()[0].samples
    buckets: list[tuple[float, float]] = []
    total = 0.0
    for s in samples:
        if s.name.endswith("_bucket"):
            le = s.labels.get("le", "+Inf")
            count = s.value
            if le != "+Inf":
                buckets.append((float(le), count))
            total = max(total, count)
    if not total or not buckets:
        return 0.0
    target = total * 0.95
    for le, count in buckets:
        if count >= target:
            return le * 1000.0
    return buckets[-1][0] * 1000.0
