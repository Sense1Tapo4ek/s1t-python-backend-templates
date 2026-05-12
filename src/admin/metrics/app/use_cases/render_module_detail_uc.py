"""Detail page render: look up plugin by slug, fetch detail, render HTML."""

from dataclasses import dataclass

from ...domain import ModuleDetailVo, UnknownModuleError
from ..interfaces import IModulePluginRegistry


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderModuleDetailUc:
    _registry: IModulePluginRegistry

    async def __call__(self, slug: str) -> tuple[ModuleDetailVo, str]:
        plugin = self._registry.find(slug)
        if plugin is None:
            raise UnknownModuleError(slug=slug)
        detail = await plugin.detail()
        html = plugin.render_detail_html(detail)
        return detail, html
