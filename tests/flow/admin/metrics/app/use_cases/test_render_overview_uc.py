from unittest.mock import MagicMock

import pytest

from admin.metrics.app.use_cases import RenderOverviewUc
from admin.metrics.domain import (
    MetricKvVo,
    ModuleSummaryVo,
    Severity,
)

pytestmark = pytest.mark.asyncio


def _summary(slug: str) -> ModuleSummaryVo:
    return ModuleSummaryVo(
        slug=slug,
        name=slug.upper(),
        kvs=(MetricKvVo(label="x", value="1", severity=Severity.OK),),
    )


class _StubPlugin:
    def __init__(self, slug: str, summary_result=None, exc: Exception | None = None) -> None:
        self.slug = slug
        self.name = slug.upper()
        self.description = ""
        self._summary_result = summary_result or _summary(slug)
        self._exc = exc

    async def summary(self):
        if self._exc:
            raise self._exc
        return self._summary_result

    async def detail(self): ...

    def render_detail_html(self, d):
        return ""


class TestRenderOverviewUc:
    async def test_gathers_all_summaries(self) -> None:
        """
        Given a registry with 3 plugins,
        When RenderOverviewUc runs,
        Then all 3 summaries are returned in input order.
        """
        reg = MagicMock()
        reg.all.return_value = (_StubPlugin("a"), _StubPlugin("b"), _StubPlugin("c"))
        uc = RenderOverviewUc(_registry=reg)
        result = await uc()
        assert [s.slug for s in result] == ["a", "b", "c"]

    async def test_failing_plugin_yields_fallback_summary(self) -> None:
        """
        Given one plugin raises,
        When the UC runs,
        Then the result contains a fallback ModuleSummaryVo for that
        plugin (severity BAD) and the other plugins are unaffected.
        """
        reg = MagicMock()
        reg.all.return_value = (
            _StubPlugin("ok"),
            _StubPlugin("boom", exc=RuntimeError("x")),
        )
        uc = RenderOverviewUc(_registry=reg)
        result = await uc()
        assert len(result) == 2
        slugs = [s.slug for s in result]
        assert slugs == ["ok", "boom"]
        boom_summary = result[1]
        assert boom_summary.kvs[0].severity == Severity.BAD
