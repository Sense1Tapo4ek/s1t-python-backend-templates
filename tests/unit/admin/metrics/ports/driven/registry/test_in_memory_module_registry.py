import pytest

from admin.metrics.domain import (
    DuplicateSlugError,
    MetricKvVo,
    ModuleDetailVo,
    ModuleSummaryVo,
    Severity,
)
from admin.metrics.ports.driven.registry import InMemoryModulePluginRegistry


class _StubPlugin:
    def __init__(self, slug: str) -> None:
        self.name = slug.upper()
        self.slug = slug
        self.description = ""

    async def summary(self) -> ModuleSummaryVo:
        return ModuleSummaryVo(
            slug=self.slug, name=self.name,
            kvs=(MetricKvVo(label="x", value="1", severity=Severity.OK),),
        )

    async def detail(self) -> ModuleDetailVo:
        return ModuleDetailVo(slug=self.slug, name=self.name, sections=())

    def render_detail_html(self, _detail: ModuleDetailVo) -> str:
        return f"<p>{self.slug}</p>"


class TestRegistry:
    def test_find_returns_plugin(self) -> None:
        reg = InMemoryModulePluginRegistry(
            _plugins=(_StubPlugin("http"), _StubPlugin("logs"))
        )
        assert reg.find("http").slug == "http"

    def test_find_unknown_returns_none(self) -> None:
        reg = InMemoryModulePluginRegistry(_plugins=())
        assert reg.find("payments") is None

    def test_duplicate_slug_rejected(self) -> None:
        with pytest.raises(DuplicateSlugError):
            InMemoryModulePluginRegistry(
                _plugins=(_StubPlugin("http"), _StubPlugin("http"))
            )

    def test_reserved_slug_overview_rejected(self) -> None:
        with pytest.raises(ValueError):
            InMemoryModulePluginRegistry(_plugins=(_StubPlugin("overview"),))

    def test_reserved_slug_api_rejected(self) -> None:
        with pytest.raises(ValueError):
            InMemoryModulePluginRegistry(_plugins=(_StubPlugin("api"),))

    def test_all_preserves_input_order(self) -> None:
        plugins = (_StubPlugin("workers"), _StubPlugin("http"), _StubPlugin("logs"))
        reg = InMemoryModulePluginRegistry(_plugins=plugins)
        assert [p.slug for p in reg.all()] == ["workers", "http", "logs"]
