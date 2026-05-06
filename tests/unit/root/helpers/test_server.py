import pytest

from root.config import RootConfig
from root.helpers.server import start_foreground, start_nohup, stop


def test_stop_exits_and_keeps_pidfile_when_permission_denied(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = RootConfig(runtime_path=tmp_path / "runtime")
    config.runtime_path.mkdir()
    config.pidfile.write_text("123")

    def deny_signal(pid: int, signal_number: int) -> None:
        raise PermissionError

    monkeypatch.setattr("root.helpers.server.os.kill", deny_signal)

    with pytest.raises(SystemExit) as exc_info:
        stop(config)

    assert exc_info.value.code == 1
    assert config.pidfile.exists()


@pytest.mark.parametrize(
    "starter_name",
    ["start_foreground", "start_nohup"],
    ids=["foreground", "nohup"],
)
def test_starter_refuses_multi_worker_mode(
    starter_name: str,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = RootConfig(runtime_path=tmp_path / "runtime", app_workers=2)
    monkeypatch.setattr(
        "root.helpers.server.find_pid_on_port", lambda _port: None
    )
    monkeypatch.setattr(
        "root.helpers.server.ensure_runtime_dirs", lambda _cfg: None
    )

    starter = {"start_foreground": start_foreground, "start_nohup": start_nohup}[
        starter_name
    ]

    with pytest.raises(SystemExit) as exc_info:
        starter(config)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "APP_WORKERS=2" in captured.err
    assert "Refusing to start" in captured.err


def test_stop_exits_and_removes_invalid_pidfile(tmp_path) -> None:
    config = RootConfig(runtime_path=tmp_path / "runtime")
    config.runtime_path.mkdir()
    config.pidfile.write_text("not-a-pid")

    with pytest.raises(SystemExit) as exc_info:
        stop(config)

    assert exc_info.value.code == 1
    assert not config.pidfile.exists()
