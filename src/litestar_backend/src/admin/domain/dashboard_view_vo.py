from dataclasses import dataclass
from datetime import datetime, timedelta

from .build_info_vo import BuildInfoVo


@dataclass(frozen=True, slots=True, kw_only=True)
class DashboardViewVo:
    app_env: str
    now: datetime
    uptime: timedelta
    build: BuildInfoVo
