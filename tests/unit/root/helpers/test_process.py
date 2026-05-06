import subprocess

import pytest

from root.config import RootConfig
from root.helpers.process import (
    ensure_runtime_dirs,
    find_pid_on_port,
    parse_pid_from_ss_output,
)


def test_parse_pid_from_ss_output_returns_listener_pid() -> None:
    output = (
        "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
        'LISTEN 0 4096 127.0.0.1:8000 0.0.0.0:* users:(("python",pid=12345,fd=7))\n'
    )

    assert parse_pid_from_ss_output(output, 8000) == 12345


def test_parse_pid_from_ss_output_returns_none_when_port_is_absent() -> None:
    output = (
        "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
        'LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("python",pid=999,fd=7))\n'
    )

    assert parse_pid_from_ss_output(output, 8000) is None


def test_parse_pid_from_ss_output_ignores_port_substrings() -> None:
    output = (
        "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
        'LISTEN 0 4096 127.0.0.1:18000 0.0.0.0:* users:(("python",pid=999,fd=7))\n'
    )

    assert parse_pid_from_ss_output(output, 8000) is None


def test_find_pid_on_port_returns_none_when_ss_is_missing(monkeypatch) -> None:
    def raise_os_error(*args, **kwargs):
        raise OSError

    monkeypatch.setattr(subprocess, "run", raise_os_error)

    assert find_pid_on_port(8000) is None


def test_find_pid_on_port_returns_none_when_ss_times_out(monkeypatch) -> None:
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["ss"], timeout=5)

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    assert find_pid_on_port(8000) is None


def test_ensure_runtime_dirs_creates_log_and_runtime_paths(tmp_path) -> None:
    config = RootConfig(volume_path=tmp_path / "storage", runtime_path=tmp_path / "runtime")

    ensure_runtime_dirs(config)

    assert config.log_dir.is_dir()
    assert config.runtime_path.is_dir()


def test_ensure_runtime_dirs_raises_runtime_error_on_os_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = RootConfig(volume_path=tmp_path / "storage", runtime_path=tmp_path / "runtime")

    def raise_os_error(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("pathlib.Path.mkdir", raise_os_error)

    with pytest.raises(RuntimeError, match="Cannot create runtime directories"):
        ensure_runtime_dirs(config)
