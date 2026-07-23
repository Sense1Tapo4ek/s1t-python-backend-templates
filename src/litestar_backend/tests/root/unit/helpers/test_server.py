import pytest

from root.config import RootConfig
from root.helpers.server import stop


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


def test_stop_exits_and_removes_invalid_pidfile(tmp_path) -> None:
    config = RootConfig(runtime_path=tmp_path / "runtime")
    config.runtime_path.mkdir()
    config.pidfile.write_text("not-a-pid")

    with pytest.raises(SystemExit) as exc_info:
        stop(config)

    assert exc_info.value.code == 1
    assert not config.pidfile.exists()
