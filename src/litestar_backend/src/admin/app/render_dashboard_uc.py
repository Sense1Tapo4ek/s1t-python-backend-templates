from dataclasses import dataclass

from shared.app import IClock

from ..domain import BuildInfoVo, DashboardViewVo


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderDashboardUC:
    _app_env: str
    _clock: IClock
    _build_info: BuildInfoVo

    def __call__(self) -> DashboardViewVo:
        now = self._clock.now()
        return DashboardViewVo(
            app_env=self._app_env,
            now=now,
            uptime=now - self._build_info.started_at,
            build=self._build_info,
        )
