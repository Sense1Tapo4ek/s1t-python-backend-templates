from datetime import UTC, datetime, timedelta
from pathlib import Path

from admin.app.use_cases import RenderDashboardUc
from admin.domain import BuildInfoVo
from shared.config import BaseAppConfig


class _FrozenClock:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        return self._value


def _build(app_name: str, started: datetime) -> BuildInfoVo:
    return BuildInfoVo(
        app_name=app_name,
        started_at=started,
        commit_sha="abc123",
        branch="main",
        dirty=False,
    )


def test_dashboard_reports_uptime(tmp_path: Path) -> None:
    config = BaseAppConfig(volume_path=tmp_path)
    started = datetime(2026, 4, 29, 12, tzinfo=UTC)
    now = started + timedelta(minutes=5)

    use_case = RenderDashboardUc(
        _config=config,
        _clock=_FrozenClock(now),
        _build_info=_build(config.app_name, started),
    )

    view = use_case()

    assert view.uptime == timedelta(minutes=5)
    assert view.app_env == "dev"
    assert view.build.started_at == started
    assert view.now == now
    assert view.build.commit_sha == "abc123"
    assert view.build.branch == "main"
