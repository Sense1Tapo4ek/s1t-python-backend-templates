from dataclasses import dataclass

from ...app import RenderDashboardUC
from ...domain import DashboardViewVo


@dataclass(frozen=True, slots=True, kw_only=True)
class AdminFacade:
    """Driving port for the admin operator: the admin dashboard surface.

    Public entry point of the `admin` context, called by the admin
    controller. Thin -- delegates to a use case and returns a domain view
    value, holding no logic of its own.
    """

    _render_dashboard_uc: RenderDashboardUC

    def render_dashboard(self) -> DashboardViewVo:
        """Build the dashboard view (app name + git build metadata).

        Called by the admin controller on a dashboard page request. Returns
        a DashboardViewVo snapshot for template rendering. Pure read; no
        external I/O and no errors propagated.
        """
        return self._render_dashboard_uc()
