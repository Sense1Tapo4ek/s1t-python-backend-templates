from datetime import timedelta
from html import escape as html_escape

import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.response import Response

from auth.ports.driving import require_role
from shared.domain.auth import Role

from ....ports.driving.facades import AdminFacade

_log = structlog.get_logger(__name__)


_DASHBOARD_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Admin · {app_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/admin/logs/static/style.css" />
</head>
<body>
<div class="app app--page">
  <header class="topbar">
    <div class="brand">
      <span class="title">{app_name}</span>
      <span class="path">/<em>admin</em></span>
    </div>
    <div class="topbar-right">
      <span>env · {app_env}</span>
      <span>uptime · {uptime}</span>
    </div>
  </header>

  <main class="dashboard-main">
    <section class="panel">
      <h2>Overview</h2>
      <div class="metric"><span class="label">app</span><span class="value">{app_name}</span></div>
      <div class="metric"><span class="label">env</span><span class="value">{app_env}</span></div>
      <div class="metric"><span class="label">started</span><span class="value">{started_at}</span></div>
      <div class="metric"><span class="label">uptime</span><span class="value">{uptime}</span></div>
      <div class="metric"><span class="label">now</span><span class="value">{now}</span></div>
    </section>

    <section class="panel">
      <h2>Build</h2>
      <div class="metric"><span class="label">commit</span><span class="value">{commit_short}</span></div>
      <div class="metric"><span class="label">branch</span><span class="value">{branch}</span></div>
      <div class="metric"><span class="label">dirty</span><span class="value">{dirty}</span></div>
    </section>

    <section class="panel">
      <h2>Tools</h2>
      <p style="color:var(--ink-muted); font-size:12px; margin:0 0 16px 0;">
        Operational surfaces.
      </p>
      <div class="actions">
        <a class="btn-link primary" href="/admin/logs">logs <span class="arrow">→</span></a>
        <a class="btn-link" href="/health">/health <span class="arrow">→</span></a>
        <a class="btn-link" href="/ping">/ping <span class="arrow">→</span></a>
        <form method="post" action="/admin/logout" style="display:contents;">
          <button type="submit" class="btn-link">
            logout <span class="arrow">→</span>
          </button>
        </form>
      </div>
    </section>
  </main>

  <footer class="statusbar">
    <span class="grow"></span>
    <span>{app_name} · admin</span>
  </footer>
</div>
</body>
</html>"""


class AdminController(Controller):
    path = "/admin"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012

    @get("/")
    @inject
    async def dashboard(self, facade: FromDishka[AdminFacade]) -> Response[str]:
        view = facade.render_dashboard()
        _log.info(
            "dashboard rendered",
            app_name=view.build.app_name,
            app_env=view.app_env,
            uptime_s=int(view.uptime.total_seconds()),
            commit_sha=view.build.commit_sha,
        )
        # Values may originate from config or git (branch can be arbitrary
        # text); escape everything so a poisoned branch name cannot inject
        # script into the dashboard.
        html = _DASHBOARD_TEMPLATE.format(
            app_name=html_escape(view.build.app_name),
            app_env=html_escape(view.app_env),
            started_at=view.build.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            now=view.now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            uptime=_format_uptime(view.uptime),
            commit_short=_short_sha(view.build.commit_sha),
            branch=html_escape(view.build.branch or "—"),
            dirty="yes" if view.build.dirty else "no",
        )
        return Response(content=html, media_type="text/html")


def _format_uptime(td: timedelta) -> str:
    total = int(td.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    return f"{minutes}m {seconds:02d}s"


def _short_sha(sha: str) -> str:
    if sha == "unknown":
        return sha
    return sha[:8] if len(sha) > 8 else sha
