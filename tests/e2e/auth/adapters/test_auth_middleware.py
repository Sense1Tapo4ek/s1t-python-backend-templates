"""End-to-end tests for AuthMiddleware + login flow.

The middleware no longer rejects requests directly — it always sets a
Principal (UNKNOWN if no/invalid credentials). Authorization happens via
`require_role` guards on protected controllers.

Admin HTML routes get redirected to /admin/login (303); JSON/API routes
get a 401/403 response.
"""

from pathlib import Path

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_303_SEE_OTHER,
    HTTP_401_UNAUTHORIZED,
)
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app


@pytest.fixture(autouse=True)
def _set_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)


@pytest.fixture
def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"}


def test_admin_html_without_auth_redirects_to_login() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get(
            "/admin/",
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_303_SEE_OTHER
    assert "/admin/login" in response.headers["location"]
    assert "next=" in response.headers["location"]


def test_admin_html_with_wrong_token_redirects_to_login() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get(
            "/admin/",
            headers={"Authorization": "Bearer wrong", "Accept": "text/html"},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_303_SEE_OTHER
    assert "/admin/login" in response.headers["location"]


def test_admin_with_correct_token_returns_200(headers: dict[str, str]) -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get("/admin/", headers=headers)
    assert response.status_code == HTTP_200_OK


def test_admin_with_cookie_token_returns_200() -> None:
    app = create_app()
    with TestClient(app=app, cookies={"admin_token": E2E_ADMIN_TOKEN}) as client:
        response = client.get("/admin/")
    assert response.status_code == HTTP_200_OK


def test_health_no_token_required() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get("/health")
    assert response.status_code == HTTP_200_OK


def test_static_logs_no_token_required() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get("/admin/logs/static/style.css")
    # 200 if the file exists, 404 if not — the point is: NOT a redirect/401.
    assert response.status_code != HTTP_401_UNAUTHORIZED
    assert response.status_code != HTTP_303_SEE_OTHER


def test_ping_no_token_required() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get("/ping")
    assert response.status_code == HTTP_200_OK


def test_login_form_accessible_to_anonymous() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get("/admin/login")
    assert response.status_code == HTTP_200_OK
    assert "text/html" in response.headers["content-type"]


def test_delete_logs_without_token_returns_401() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.delete(
            "/api/v1/admin/logs?confirm=yes-i-am-sure",
            headers={"Accept": "application/json"},
        )
    assert response.status_code == HTTP_401_UNAUTHORIZED


def test_delete_logs_with_token_succeeds(headers: dict[str, str]) -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.delete(
            "/api/v1/admin/logs?confirm=yes-i-am-sure",
            headers=headers,
        )
    assert response.status_code == HTTP_200_OK


def test_admin_api_with_wrong_token_returns_401() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.delete(
            "/api/v1/admin/logs?confirm=yes-i-am-sure",
            headers={"Authorization": "Bearer wrong", "Accept": "application/json"},
        )
    assert response.status_code == HTTP_401_UNAUTHORIZED


def test_malformed_basic_header_treated_as_unauthenticated() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.delete(
            "/api/v1/admin/logs?confirm=yes-i-am-sure",
            headers={"Authorization": "Basic xxx", "Accept": "application/json"},
        )
    assert response.status_code == HTTP_401_UNAUTHORIZED


def test_empty_bearer_token_treated_as_unauthenticated() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.delete(
            "/api/v1/admin/logs?confirm=yes-i-am-sure",
            headers={"Authorization": "Bearer ", "Accept": "application/json"},
        )
    assert response.status_code == HTTP_401_UNAUTHORIZED
