from datetime import timedelta

import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.response import Template

from auth.ports.driving import require_role
from shared.domain.auth import Role

from ....ports.driving.facades import AdminFacade

_log = structlog.get_logger(__name__)


class AdminController(Controller):
    path = "/admin"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012
    tags = ["Admin UI"]  # noqa: RUF012

    @get("/")
    @inject
    async def dashboard(
        self,
        facade: FromDishka[AdminFacade],
    ) -> Template:
        """Render the admin dashboard HTML page."""
        view = facade.render_dashboard()
        _log.info(
            "dashboard rendered",
            app_name=view.build.app_name,
            app_env=view.app_env,
            uptime_s=int(view.uptime.total_seconds()),
            commit_sha=view.build.commit_sha,
        )
        # Jinja auto-escapes; passing raw values is safe even when build
        # metadata (e.g. branch name) originates from arbitrary git refs.
        return Template(
            template_name="admin/dashboard.html",
            context={
                "app_name": view.build.app_name,
                "app_env": view.app_env,
                "started_at": view.build.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "now": view.now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "uptime": _format_uptime(view.uptime),
                "commit_short": _short_sha(view.build.commit_sha),
                "branch": view.build.branch or "—",
                "dirty": "yes" if view.build.dirty else "no",
            },
        )


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
