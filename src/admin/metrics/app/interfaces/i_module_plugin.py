from typing import Protocol

from ...domain import ModuleDetailVo, ModuleSummaryVo


class IMetricsModulePlugin(Protocol):
    """Pluggable metrics module. See spec section 4 for full contract."""

    name: str
    slug: str
    description: str

    async def summary(self) -> ModuleSummaryVo: ...
    async def detail(self) -> ModuleDetailVo: ...
    def render_detail_html(self, detail: ModuleDetailVo) -> str: ...
