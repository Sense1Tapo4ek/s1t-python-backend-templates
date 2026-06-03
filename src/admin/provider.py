from datetime import UTC, datetime

from dishka import Provider, Scope, provide

from shared.config import BaseAppConfig

from .adapters.driven.build_info.git_build_info import resolve_build_meta
from .app.use_cases import RenderDashboardUc
from .domain import BuildInfoVo
from .ports.driving import AdminFacade


class AdminProvider(Provider):
    scope = Scope.APP

    @provide
    def build_info(self, config: BaseAppConfig) -> BuildInfoVo:
        sha, branch, dirty = resolve_build_meta()
        return BuildInfoVo(
            app_name=config.app_name,
            started_at=datetime.now(UTC),
            commit_sha=sha or "unknown",
            branch=branch,
            dirty=dirty,
        )

    render_dashboard_uc = provide(RenderDashboardUc)
    admin_facade = provide(AdminFacade)
