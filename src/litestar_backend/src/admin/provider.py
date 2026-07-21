from datetime import UTC, datetime

from dishka import Provider, Scope, provide

from shared.app import IClock
from shared.config import BaseAppConfig

from .adapters.driven.git_build_info import resolve_build_meta
from .app import RenderDashboardUC
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

    @provide
    def render_dashboard_uc(
        self, config: BaseAppConfig, clock: IClock, build_info: BuildInfoVo
    ) -> RenderDashboardUC:
        return RenderDashboardUC(
            _app_env=config.app_env.value,
            _clock=clock,
            _build_info=build_info,
        )

    admin_facade = provide(AdminFacade)
