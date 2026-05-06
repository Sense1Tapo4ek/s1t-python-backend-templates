from dataclasses import dataclass

from shared.config import BaseAppConfig

from ...app.interfaces import IClock
from ...domain import BuildInfoVo, DashboardViewVo


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderDashboardUc:
    _config: BaseAppConfig
    _clock: IClock
    _build_info: BuildInfoVo

    def __call__(self) -> DashboardViewVo:
        now = self._clock.now()
        return DashboardViewVo(
            app_env=self._config.app_env.value,
            now=now,
            uptime=now - self._build_info.started_at,
            build=self._build_info,
        )
