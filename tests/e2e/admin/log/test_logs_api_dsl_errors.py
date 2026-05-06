"""End-to-end check that DslSyntaxError surfaces as HTTP 400 with position+reason."""

from pathlib import Path

import pytest
from litestar.status_codes import HTTP_400_BAD_REQUEST
from litestar.testing import TestClient

from root.entrypoints.api import create_app


def test_invalid_dsl_returns_400_with_position_and_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    """
    Given a request to /api/v1/admin/logs with q=level:VERBOSE,
    When the facade parses the DSL,
    Then DslSyntaxError surfaces as 400 with structured body.
    """
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/api/v1/admin/logs?q=level:VERBOSE", headers=auth_headers)

    assert response.status_code == HTTP_400_BAD_REQUEST
    body = response.json()
    assert "position" in body
    assert "reason" in body
    assert "unknown log level" in body["reason"]


def test_invalid_kv_key_returns_400(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/api/v1/admin/logs?q=kv.weird-key=1", headers=auth_headers)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "invalid characters" in response.json()["reason"]


def test_valid_dsl_returns_200_empty_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))

    app = create_app()

    with TestClient(app=app) as client:
        response = client.get("/api/v1/admin/logs?q=level:WARN%2B", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == []
    assert body["cursor"] is None
