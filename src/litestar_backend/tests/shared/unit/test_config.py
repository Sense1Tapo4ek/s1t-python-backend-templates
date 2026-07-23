import tempfile
from pathlib import Path

from shared.config import BaseAppConfig


def test_base_app_config_default_volume_path_is_next_to_src() -> None:
    config = BaseAppConfig()

    assert config.volume_path == config.project_root / "storage"
    assert config.volume_path.parent == config.project_root


def test_base_app_config_log_dir_lives_inside_volume_path(tmp_path: Path) -> None:
    config = BaseAppConfig(volume_path=tmp_path)

    assert config.log_dir == tmp_path / "logs"


def test_base_app_config_default_runtime_path_uses_app_name() -> None:
    config = BaseAppConfig(app_name="custom-service")

    assert config.runtime_path == Path(tempfile.gettempdir()) / "custom-service"


def test_base_app_config_resolves_relative_runtime_path_from_project_root() -> None:
    config = BaseAppConfig(runtime_path=Path("tmp/app-runtime"))

    assert config.runtime_path == config.project_root / "tmp/app-runtime"


def test_base_app_config_resolves_relative_volume_path_from_project_root() -> None:
    config = BaseAppConfig(volume_path=Path("var/storage"))

    assert config.volume_path == config.project_root / "var/storage"
