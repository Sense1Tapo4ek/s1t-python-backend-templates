from pathlib import Path

import pytest
from litestar.status_codes import HTTP_200_OK
from litestar.testing import TestClient

from root.entrypoints.api import create_app


def test_logs_api_returns_empty_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/api/v1/admin/logs", headers=auth_headers)

    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["entries"] == []
    assert data["cursor"] is None


def test_logs_export_ndjson_default_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/api/v1/admin/logs/export", headers=auth_headers)

    assert response.status_code == HTTP_200_OK
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert "logs.ndjson" in response.headers["content-disposition"]
    # No log entries yet → empty body (NDJSON is just zero lines, not "[]").
    assert response.text == ""


def test_logs_export_returns_csv_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/api/v1/admin/logs/export?format=csv", headers=auth_headers)

    assert response.status_code == HTTP_200_OK
    # New CSV header includes the `context` column (folded raw_json kwargs).
    assert response.text.startswith("id,timestamp,level,logger,event,pathname,lineno,func_name,context")


def test_logs_export_unknown_format_returns_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/admin/logs/export?format=xml",
            headers=auth_headers,
        )

    assert response.status_code == 400
