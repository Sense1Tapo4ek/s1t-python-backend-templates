from unittest.mock import MagicMock

import pytest

from admin.metrics.app.use_cases import RenderModuleDetailUc
from admin.metrics.domain import (
    DetailSectionVo,
    ModuleDetailVo,
    UnknownModuleError,
)

pytestmark = pytest.mark.asyncio


class _StubPlugin:
    slug = "x"
    name = "X"
    description = ""

    async def summary(self): ...

    async def detail(self):
        return ModuleDetailVo(
            slug="x",
            name="X",
            sections=(DetailSectionVo(title="t", payload={}),),
        )

    def render_detail_html(self, d):
        return "<p>x</p>"


class TestRenderModuleDetailUc:
    async def test_returns_detail_and_html(self) -> None:
        """
        Given a registry that finds the plugin,
        When RenderModuleDetailUc runs with matching slug,
        Then it returns (ModuleDetailVo, rendered HTML).
        """
        reg = MagicMock()
        reg.find.return_value = _StubPlugin()
        uc = RenderModuleDetailUc(_registry=reg)
        detail, html = await uc(slug="x")
        assert detail.slug == "x"
        assert "<p>" in html

    async def test_unknown_slug_raises(self) -> None:
        """
        Given a registry that returns None for the slug,
        When RenderModuleDetailUc runs,
        Then UnknownModuleError is raised.
        """
        reg = MagicMock()
        reg.find.return_value = None
        uc = RenderModuleDetailUc(_registry=reg)
        with pytest.raises(UnknownModuleError):
            await uc(slug="missing")
