import pytest

from root.config import RootConfig


def test_root_config_can_be_created_without_env_file() -> None:
    config = RootConfig()

    assert config.app_name == "litestar-base"
    assert config.app_host == "127.0.0.1"
    assert config.app_port == 8000
    assert config.app_workers == 1
    assert config.src_dir.name == "src"
    assert config.project_root == config.src_dir.parent


def test_root_config_derives_pidfile_from_runtime_path() -> None:
    config = RootConfig()

    assert config.pidfile == config.runtime_path / "litestar-base.pid"


def test_root_config_console_log_lives_in_log_dir() -> None:
    config = RootConfig()

    assert config.console_log == config.log_dir / "litestar-base.log"


def test_root_config_reads_workers_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_WORKERS", "3")

    config = RootConfig()

    assert config.app_workers == 3


def test_root_config_should_reload_in_dev() -> None:
    config = RootConfig()

    assert config.should_reload is True


def test_root_config_should_not_reload_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", "prod-token")

    config = RootConfig()

    assert config.should_reload is False
