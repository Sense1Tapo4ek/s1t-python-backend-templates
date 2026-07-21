from datetime import UTC, datetime, timedelta

from admin.app import RenderDashboardUC
from admin.domain import BuildInfoVo


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


def test_dashboard_reports_uptime() -> None:
    started = datetime(2026, 4, 29, 12, tzinfo=UTC)
    now = started + timedelta(minutes=5)

    use_case = RenderDashboardUC(
        _app_env="dev",
        _clock=_FrozenClock(now),
        _build_info=_build("litestar-base", started),
    )

    view = use_case()

    assert view.uptime == timedelta(minutes=5)
    assert view.app_env == "dev"
    assert view.build.started_at == started
    assert view.now == now
    assert view.build.commit_sha == "abc123"
    assert view.build.branch == "main"
