import os
from pathlib import Path

import pytest
from litestar.status_codes import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
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


def test_ready_endpoint_returns_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/health/ready")

    assert response.status_code == HTTP_200_OK
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"log_dir": "up", "postgres": "up", "valkey": "up"}


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory write perms")
def test_ready_returns_503_when_log_dir_not_writable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        # Lifespan has created <volume>/logs by now; strip write perms so the
        # readiness probe's touch() fails.
        log_dir = tmp_path / "logs"
        log_dir.chmod(0o500)
        try:
            response = client.get("/health/ready")
        finally:
            log_dir.chmod(0o700)

    assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE


def test_ping_endpoint_returns_pong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/ping")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"message": "pong"}


def test_ready_returns_200_with_all_checks_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given infra up, When GET /health/ready, Then 200 and all checks up."""
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        resp = client.get("/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"log_dir": "up", "postgres": "up", "valkey": "up"}
