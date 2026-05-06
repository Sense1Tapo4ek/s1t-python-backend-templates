from dataclasses import dataclass

from ....app.use_cases import RenderDashboardUc
from ....domain import DashboardViewVo


@dataclass(frozen=True, slots=True, kw_only=True)
class AdminFacade:
    _render_dashboard_uc: RenderDashboardUc

    def render_dashboard(self) -> DashboardViewVo:
        return self._render_dashboard_uc()
