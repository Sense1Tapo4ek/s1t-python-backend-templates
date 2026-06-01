from pathlib import Path

import pytest


def test_db_path_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_NAME", "x")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    from db_example_litestar.config import DbExampleLitestarConfig

    cfg = DbExampleLitestarConfig()
    assert cfg.db_path == tmp_path / "db_example_litestar.db"
