"""Concurrent summary collection for the overview page.

Failing plugins yield a fallback `ModuleSummaryVo` with severity=BAD
instead of taking the whole page down. The error is logged with the
plugin slug for triage.
"""

import asyncio
from dataclasses import dataclass

import structlog

from ...domain import MetricKvVo, ModuleSummaryVo, Severity
from ..interfaces import IMetricsModulePlugin, IModulePluginRegistry

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderOverviewUc:
    _registry: IModulePluginRegistry

    async def __call__(self) -> tuple[ModuleSummaryVo, ...]:
        plugins = tuple(self._registry.all())
        results = await asyncio.gather(
            *(self._safe_summary(p) for p in plugins),
            return_exceptions=False,
        )
        return tuple(results)

    async def _safe_summary(
        self, plugin: IMetricsModulePlugin
    ) -> ModuleSummaryVo:
        try:
            return await plugin.summary()
        except Exception as exc:
            _log.exception(
                "plugin summary failed",
                plugin=plugin.slug,
                error_type=type(exc).__name__,
            )
            return ModuleSummaryVo(
                slug=plugin.slug,
                name=plugin.name,
                kvs=(
                    MetricKvVo(
                        label="status",
                        value="module failed to report",
                        severity=Severity.BAD,
                    ),
                ),
            )
