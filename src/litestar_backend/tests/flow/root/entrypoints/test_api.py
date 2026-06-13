from pathlib import Path

import pytest
from litestar import Litestar

from root.entrypoints.api import create_app


def test_create_app_returns_litestar_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    assert isinstance(app, Litestar)
