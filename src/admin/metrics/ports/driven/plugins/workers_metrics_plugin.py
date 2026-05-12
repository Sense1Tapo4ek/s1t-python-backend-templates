"""Workers module - process-level cross-cutting view.

Reads Valkey hashes populated by RedisMetricsPublisher. Owns its
severity thresholds (rss/loop_lag) as plugin constants - projects with
different SLOs subclass to override.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape as html_escape
from typing import Any, Protocol

from ....domain import (
    DetailSectionVo,
    MetricKvVo,
    ModuleDetailVo,
    ModuleSummaryVo,
    Severity,
    classify,
)


_RSS_WARN_BYTES = 256 * 1024 * 1024
_RSS_BAD_BYTES = 512 * 1024 * 1024
_LOOP_WARN_MS = 10.0
_LOOP_BAD_MS = 100.0


class IRedisClient(Protocol):
    def scan_iter(self, match: str, count: int = 100) -> AsyncIterator[Any]: ...

    async def hgetall(self, key: Any) -> Any: ...


@dataclass(slots=True, kw_only=True)
class WorkersMetricsPlugin:
    _redis: IRedisClient
    _key_prefix: str
    name: str = "Workers"
    slug: str = "workers"
    description: str = "processes - memory - loop"

    async def summary(self) -> ModuleSummaryVo:
        rows = await self._load()
        alive = len(rows)
        api = sum(1 for r in rows if r["role"] == "api")
        sink = sum(1 for r in rows if r["role"] == "sink")
        max_rss = max((r["rss_bytes"] for r in rows), default=0)
        max_loop = max((r["loop_lag_p95_ms"] for r in rows), default=0.0)

        return ModuleSummaryVo(
            slug=self.slug, name=self.name,
            kvs=(
                MetricKvVo(
                    label="alive",
                    value=f"{alive} (api {api} | sink {sink})",
                    severity=Severity.OK if alive > 0 else Severity.BAD,
                ),
                MetricKvVo(
                    label="rss - max",
                    value=_fmt_bytes(max_rss),
                    severity=classify(max_rss, warn=_RSS_WARN_BYTES, bad=_RSS_BAD_BYTES),
                ),
                MetricKvVo(
                    label="loop p95 - max",
                    value=f"{max_loop:.1f} ms",
                    severity=classify(max_loop, warn=_LOOP_WARN_MS, bad=_LOOP_BAD_MS),
                ),
            ),
        )

    async def detail(self) -> ModuleDetailVo:
        rows = await self._load()
        now = datetime.now(timezone.utc)
        enriched = [
            {
                **row,
                "uptime_s": int(
                    (now - _parse_dt(row["started_at"])).total_seconds()
                ) if row["started_at"] else 0,
                "rss_severity": classify(
                    row["rss_bytes"], warn=_RSS_WARN_BYTES, bad=_RSS_BAD_BYTES
                ).value,
                "loop_severity": classify(
                    row["loop_lag_p95_ms"], warn=_LOOP_WARN_MS, bad=_LOOP_BAD_MS
                ).value,
            }
            for row in rows
        ]
        section = DetailSectionVo(
            title="Worker list",
            payload={"rows": enriched},
        )
        return ModuleDetailVo(slug=self.slug, name=self.name, sections=(section,))

    def render_detail_html(self, detail: ModuleDetailVo) -> str:
        rows = detail.sections[0].payload.get("rows", []) if detail.sections else []
        body = "".join(
            f"<tr>"
            f"<td>{html_escape(r['worker_id'])}</td>"
            f"<td>{html_escape(r['role'])}</td>"
            f"<td>{html_escape(r['started_at'])}</td>"
            f"<td>{_fmt_uptime(r['uptime_s'])}</td>"
            f"<td class='sev-{r['rss_severity']}'>{_fmt_bytes(r['rss_bytes'])}</td>"
            f"<td class='sev-{r['loop_severity']}'>{r['loop_lag_p95_ms']:.1f} ms</td>"
            f"</tr>"
            for r in rows
        )
        return (
            "<section class='panel'>"
            "<h2>Worker list</h2>"
            "<table class='workers-table'>"
            "<thead><tr><th>worker_id</th><th>role</th><th>started</th>"
            "<th>uptime</th><th>rss</th><th>loop p95</th></tr></thead>"
            f"<tbody>{body}</tbody>"
            "</table>"
            "</section>"
        )

    async def _load(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        async for key in self._redis.scan_iter(
            match=f"{self._key_prefix}*", count=200
        ):
            raw = await self._redis.hgetall(key)
            if not raw:
                continue
            fields = {_decode(k): _decode(v) for k, v in raw.items()}
            rows.append({
                "role": fields.get("role", ""),
                "worker_id": fields.get("worker_id", ""),
                "started_at": fields.get("started_at", ""),
                "rss_bytes": int(_safe_float(fields.get("rss_bytes")) or 0),
                "loop_lag_p95_ms": _safe_float(fields.get("loop_lag_p95_ms")) or 0.0,
            })
        rows.sort(key=lambda r: (r["role"], r["worker_id"]))
        return rows


def _decode(v: Any) -> str:
    return v.decode() if isinstance(v, bytes) else str(v)


def _safe_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_dt(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.now(timezone.utc)


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    units = ("KB", "MB", "GB", "TB")
    value = float(n)
    unit = "B"
    for u in units:
        value /= 1024
        unit = u
        if value < 1024:
            break
    return f"{value:.0f} {unit}" if value >= 100 else f"{value:.1f} {unit}"


def _fmt_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"
