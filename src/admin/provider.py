from dishka import Provider, Scope, provide

from shared.config import BaseAppConfig

from .adapters.driven.build_info.git_build_info import resolve_build_info
from .app.interfaces import IClock
from .app.use_cases import RenderDashboardUc
from .domain import BuildInfoVo
from .ports.driven.gateways import SystemClockGateway
from .ports.driving.facades import AdminFacade


class AdminProvider(Provider):
    scope = Scope.APP

    clock = provide(SystemClockGateway, provides=IClock)

    @provide
    def build_info(self, config: BaseAppConfig) -> BuildInfoVo:
        return resolve_build_info(app_name=config.app_name)

    render_dashboard_uc = provide(RenderDashboardUc)
    admin_facade = provide(AdminFacade)
