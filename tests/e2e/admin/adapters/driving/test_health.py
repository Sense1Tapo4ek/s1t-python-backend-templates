from pathlib import Path

import pytest
from litestar.status_codes import HTTP_200_OK
from litestar.testing import TestClient

from root.entrypoints.api import create_app


def test_health_endpoint_returns_build_info(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    monkeypatch.setenv("GIT_COMMIT_SHA", "deadbeef1234")
    monkeypatch.setenv("GIT_BRANCH", "feature-x")
    monkeypatch.setenv("GIT_DIRTY", "1")

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/health")

    assert response.status_code == HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "test-service"
    assert body["commit"] == "deadbeef1234"
    assert body["branch"] == "feature-x"
    assert body["dirty"] is True
    assert "started_at" in body


def test_ping_endpoint_returns_pong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/ping")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"message": "pong"}
