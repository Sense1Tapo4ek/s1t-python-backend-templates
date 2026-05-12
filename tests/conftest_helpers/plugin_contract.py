"""Shared assertion: any plugin must satisfy the basic contract.

Imported from every plugin test. Future modules pick it up automatically.
"""

from admin.metrics.app.interfaces import IMetricsModulePlugin
from admin.metrics.domain import ModuleDetailVo, ModuleSummaryVo


async def assert_plugin_contract(plugin: IMetricsModulePlugin) -> None:
    assert plugin.name, "plugin.name must be non-empty"
    assert plugin.slug, "plugin.slug must be non-empty"
    assert plugin.description is not None
    summary = await plugin.summary()
    assert isinstance(summary, ModuleSummaryVo)
    assert summary.slug == plugin.slug
    assert len(summary.kvs) >= 1, "summary must contain at least one KV"
    detail = await plugin.detail()
    assert isinstance(detail, ModuleDetailVo)
    assert detail.slug == plugin.slug
    html = plugin.render_detail_html(detail)
    assert isinstance(html, str) and html, "render_detail_html must return non-empty str"
    lo = html.lower()
    assert "<html" not in lo and "<body" not in lo, (
        "render_detail_html returns a fragment, not a full document"
    )
