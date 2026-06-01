from pathlib import Path

import pytest


def test_db_path_defaults_under_volume(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    from db_example.config import DbExampleConfig

    cfg = DbExampleConfig()
    assert cfg.db_path == tmp_path / "db_example.db"
    assert cfg.pool_size == 4
