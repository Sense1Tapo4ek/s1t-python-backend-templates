from pathlib import Path

import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient

from root.entrypoints.api import create_app


def test_create_app_returns_litestar_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    assert isinstance(app, Litestar)


@pytest.mark.asyncio
async def test_create_app_smoke_health(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()
    async with AsyncTestClient(app=app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "test-service"
