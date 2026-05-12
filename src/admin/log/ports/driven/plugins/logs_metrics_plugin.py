"""Logs module plugin — reads pipeline state for the dashboard.

Sources:
- producer-queue depth: from RedisStreamPublisher (this process)
- dropped_total: shared.logging._QueueLogger class field
- stream length: XLEN
- sink pending: XPENDING summary
"""

from dataclasses import dataclass
from html import escape as html_escape
from typing import Any

from admin.metrics.domain import (
    DetailSectionVo,
    MetricKvVo,
    ModuleDetailVo,
    ModuleSummaryVo,
    classify,
)

from shared.logging import _QueueLogger

from ..gateways.redis_stream_publisher import RedisStreamPublisher


@dataclass(slots=True, kw_only=True)
class LogsMetricsPlugin:
    _redis: Any
    _publisher: RedisStreamPublisher
    _stream_key: str
    _consumer_group: str
    _stream_maxlen: int
    _batch_size: int
    name: str = "Logs"
    slug: str = "logs"
    description: str = "pipeline - sink - stream"

    async def summary(self) -> ModuleSummaryVo:
        stream_len = await self._safe_xlen()
        pending = await self._safe_pending()
        dropped = int(_QueueLogger._dropped_total)

        return ModuleSummaryVo(
            slug=self.slug,
            name=self.name,
            kvs=(
                MetricKvVo(
                    label="dropped - 5m",
                    value=str(dropped),
                    severity=classify(dropped, warn=None, bad=1),
                ),
                MetricKvVo(
                    label="stream length",
                    value=f"{stream_len:,}",
                    severity=classify(
                        stream_len,
                        warn=self._stream_maxlen * 0.5,
                        bad=self._stream_maxlen * 0.8,
                    ),
                ),
                MetricKvVo(
                    label="sink pending",
                    value=str(pending),
                    severity=classify(
                        pending,
                        warn=self._batch_size * 3,
                        bad=self._batch_size * 10,
                    ),
                ),
            ),
        )

    async def detail(self) -> ModuleDetailVo:
        s = await self.summary()
        return ModuleDetailVo(
            slug=self.slug,
            name=self.name,
            sections=(
                DetailSectionVo(
                    title="KPI",
                    payload={"kvs": [(kv.label, kv.value) for kv in s.kvs]},
                ),
                DetailSectionVo(
                    title="Pipeline (this worker)",
                    payload={
                        "queue_depth": self._publisher.buffer.qsize(),
                        "dropped_total": int(_QueueLogger._dropped_total),
                    },
                ),
            ),
        )

    def render_detail_html(self, detail: ModuleDetailVo) -> str:
        sections = detail.sections
        kpi = sections[0].payload.get("kvs", []) if sections else []
        kpi_html = "".join(
            f"<div class='metric'><span class='label'>{html_escape(l)}</span>"
            f"<span class='value'>{html_escape(v)}</span></div>"
            for (l, v) in kpi
        )
        pl = sections[1].payload if len(sections) > 1 else {}
        return (
            "<section class='panel'><h2>KPI</h2>"
            f"{kpi_html}"
            "</section>"
            "<section class='panel'><h2>Pipeline (this worker)</h2>"
            f"<div class='metric'><span class='label'>queue depth</span>"
            f"<span class='value'>{int(pl.get('queue_depth', 0))}</span></div>"
            f"<div class='metric'><span class='label'>dropped total</span>"
            f"<span class='value'>{int(pl.get('dropped_total', 0))}</span></div>"
            "</section>"
        )

    async def _safe_xlen(self) -> int:
        try:
            return int(await self._redis.xlen(self._stream_key))
        except Exception:
            return 0

    async def _safe_pending(self) -> int:
        try:
            resp = await self._redis.xpending(
                self._stream_key, self._consumer_group
            )
            if isinstance(resp, dict):
                return int(resp.get("pending", 0))
            if isinstance(resp, (list, tuple)) and resp:
                return int(resp[0])
            return int(resp or 0)
        except Exception:
            return 0
