from pathlib import Path

import pytest


def test_db_path_defaults_under_volume(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    from db_example_sddd.config import DbExampleSdddConfig

    cfg = DbExampleSdddConfig()
    assert cfg.db_path == tmp_path / "db_example_sddd.db"
    assert cfg.pool_size == 4
