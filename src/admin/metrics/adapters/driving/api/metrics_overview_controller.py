from html import escape as html_escape

import msgspec
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.exceptions import NotFoundException

from auth.ports.driving import require_role
from shared.domain.auth import Role

from ....app.interfaces import IModulePluginRegistry
from ....app.use_cases import RenderModuleDetailUc, RenderOverviewUc
from ....config import MetricsConfig
from ....domain import ModuleSummaryVo, UnknownModuleError
from ....ports.driving.schemas import (
    ModuleKvResponse,
    ModuleSummaryResponse,
    OverviewResponse,
)

_DETAIL_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>Admin &middot; Metrics &middot; {name}</title>
<link rel="stylesheet" href="/admin/metrics/static/style.css"/>
</head><body>
<div class="app app--page">
  <header class="topbar">
    <div class="brand">
      <span class="title">litestar-base</span>
      <span class="path">/<em>admin &middot; metrics &middot; {slug}</em></span>
    </div>
    <nav><a class="btn" href="/admin/metrics/">&larr; overview</a></nav>
  </header>
  <main class="metrics-detail" data-slug="{slug}" data-poll-ms="{poll_ms}">
    <h2>{name}</h2>
    {body}
    <p class="footer-note">auto-refresh {poll_s}s</p>
  </main>
</div>
<script src="/admin/metrics/static/overview.js"></script>
</body></html>"""


_OVERVIEW_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>Admin &middot; Metrics &middot; {app_name}</title>
<link rel="stylesheet" href="/admin/metrics/static/style.css"/>
</head><body>
<div class="app app--page">
  <header class="topbar">
    <div class="brand">
      <span class="title">{app_name}</span>
      <span class="path">/<em>admin &middot; metrics</em></span>
    </div>
  </header>
  <main class="metrics-overview" data-poll-ms="{poll_ms}">
    <h2>Modules</h2>
    <div class="cards-grid">{cards}</div>
    <p class="footer-note">auto-refresh {poll_s}s</p>
  </main>
</div>
<script src="/admin/metrics/static/overview.js"></script>
</body></html>"""


def _render_card(s: ModuleSummaryVo) -> str:
    kvs_html = "".join(
        f"<div class='kv'><span class='k'>{html_escape(kv.label)}</span>"
        f"<span class='v sev-{kv.severity.value}'>{html_escape(kv.value)}</span>"
        f"</div>"
        for kv in s.kvs
    )
    return (
        f"<a class='modcard' href='/admin/metrics/{html_escape(s.slug)}' "
        f"data-slug='{html_escape(s.slug)}'>"
        f"<div class='arrow'>&rarr;</div>"
        f"<div class='ttl'>{html_escape(s.name)}</div>"
        f"{kvs_html}"
        f"</a>"
    )


class MetricsOverviewController(Controller):
    path = "/admin/metrics"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012

    @get("/", media_type="text/html")
    @inject
    async def overview_html(
        self,
        uc: FromDishka[RenderOverviewUc],
        config: FromDishka[MetricsConfig],
    ) -> str:
        summaries = await uc()
        cards = "".join(_render_card(s) for s in summaries)
        return _OVERVIEW_HTML.format(
            app_name="litestar-base",
            cards=cards,
            poll_ms=int(config.publish_interval_s * 1000),
            poll_s=int(config.publish_interval_s),
        )

    @get("/{slug:str}", media_type="text/html")
    @inject
    async def detail_html(
        self,
        slug: str,
        detail_uc: FromDishka[RenderModuleDetailUc],
        config: FromDishka[MetricsConfig],
    ) -> str:
        try:
            detail, body_html = await detail_uc(slug=slug)
        except UnknownModuleError as exc:
            raise NotFoundException(f"unknown metrics module: {slug}") from exc
        return _DETAIL_HTML.format(
            slug=html_escape(detail.slug),
            name=html_escape(detail.name),
            body=body_html,
            poll_ms=int(config.publish_interval_s * 1000),
            poll_s=int(config.publish_interval_s),
        )

    @get("/api", media_type="application/json")
    @inject
    async def api_endpoint(
        self,
        module: str,
        uc: FromDishka[RenderOverviewUc],
        detail_uc: FromDishka[RenderModuleDetailUc],
        registry: FromDishka[IModulePluginRegistry],
        config: FromDishka[MetricsConfig],
    ) -> bytes:
        if module == "overview":
            summaries = await uc()
            descriptions = {p.slug: p.description for p in registry.all()}
            payload = OverviewResponse(
                modules=tuple(
                    ModuleSummaryResponse(
                        slug=s.slug,
                        name=s.name,
                        description=descriptions.get(s.slug, ""),
                        kvs=tuple(
                            ModuleKvResponse(
                                label=kv.label,
                                value=kv.value,
                                severity=kv.severity.value,
                            )
                            for kv in s.kvs
                        ),
                    )
                    for s in summaries
                ),
                poll_interval_ms=int(config.publish_interval_s * 1000),
            )
            return msgspec.json.encode(payload)
        try:
            detail, _html = await detail_uc(slug=module)
        except UnknownModuleError as exc:
            raise NotFoundException(f"unknown metrics module: {module}") from exc
        return msgspec.json.encode(
            {
                "slug": detail.slug,
                "name": detail.name,
                "sections": [
                    {"title": s.title, "payload": s.payload}
                    for s in detail.sections
                ],
                "poll_interval_ms": int(config.publish_interval_s * 1000),
            }
        )
