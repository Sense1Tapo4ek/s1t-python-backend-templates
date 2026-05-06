"""End-to-end tests for the admin login flow."""

from pathlib import Path

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_303_SEE_OTHER,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from litestar.testing import TestClient

from root.entrypoints.api import create_app

TOKEN = "valid-admin-token"


@pytest.fixture(autouse=True)
def _set_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-service")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", TOKEN)


def test_login_form_renders() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get("/admin/login")
    assert response.status_code == HTTP_200_OK
    body = response.text
    assert "test-service" in body
    assert 'name="token"' in body
    assert 'method="post"' in body
    assert 'action="/admin/login"' in body


def test_login_with_valid_token_sets_cookie_and_redirects() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.post(
            "/admin/login",
            data={"token": TOKEN, "next": "/admin/"},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/admin/"
    set_cookie = response.headers.get("set-cookie", "")
    assert "admin_token=" in set_cookie
    assert TOKEN in set_cookie
    assert "HttpOnly" in set_cookie


def test_login_with_invalid_token_returns_401_with_form() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.post(
            "/admin/login",
            data={"token": "wrong"},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert "Invalid token" in response.text
    assert 'name="token"' in response.text


def test_login_with_empty_token_returns_400() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.post(
            "/admin/login",
            data={"token": ""},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "Token cannot be empty" in response.text


def test_login_open_redirect_protection() -> None:
    """`next=` must be coerced to /admin/ if it's not an internal admin path."""
    app = create_app()
    with TestClient(app=app) as client:
        response = client.post(
            "/admin/login",
            data={"token": TOKEN, "next": "https://evil.example/x"},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/admin/"


@pytest.mark.parametrize(
    "evil_next",
    [
        "//evil.example/x",            # protocol-relative
        "/\\\\evil.example",           # backslash netloc smuggle
        "/admin/../etc/passwd",        # dot-segment escape
        "javascript:alert(1)",         # script scheme
        "https://evil/admin",          # absolute URL with /admin path
    ],
)
def test_login_next_smuggle_attempts_coerce_to_dashboard(evil_next: str) -> None:
    """All known open-redirect smuggling patterns must fall back to /admin/."""
    app = create_app()
    with TestClient(app=app) as client:
        response = client.post(
            "/admin/login",
            data={"token": TOKEN, "next": evil_next},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_303_SEE_OTHER
    location = response.headers["location"]
    assert location == "/admin/", f"smuggle {evil_next!r} → {location}"


def test_login_xss_in_next_is_escaped() -> None:
    """A crafted `next` containing HTML must NOT break out of the form value."""
    app = create_app()
    payload = '/admin/"><script>alert(1)</script>'
    with TestClient(app=app) as client:
        # GET with the malicious next so the form re-renders it inside value="...".
        response = client.get(f"/admin/login?next={payload}")
    assert response.status_code == HTTP_200_OK
    body = response.text
    # The literal `<script>` tag must not appear in the rendered HTML.
    assert "<script>alert(1)</script>" not in body
    # Escaped form is fine to be present.
    assert "&lt;script&gt;" in body or "/admin/" in body


def test_login_xss_in_error_is_escaped() -> None:
    """If the error path ever receives HTML, it must be escaped."""
    # Trigger the empty-token branch — the message itself is hardcoded so we
    # only assert it does not contain unescaped HTML.
    app = create_app()
    with TestClient(app=app) as client:
        response = client.post(
            "/admin/login",
            data={"token": ""},
            follow_redirects=False,
        )
    assert "<script" not in response.text.lower().replace("&lt;", "")


def test_login_preserves_safe_next_inside_admin() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.post(
            "/admin/login",
            data={"token": TOKEN, "next": "/admin/logs"},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/admin/logs"


def test_logout_clears_cookie_and_redirects_to_login() -> None:
    app = create_app()
    with TestClient(app=app, cookies={"admin_token": TOKEN}) as client:
        response = client.post("/admin/logout", follow_redirects=False)
    assert response.status_code == HTTP_303_SEE_OTHER
    assert response.headers["location"] == "/admin/login"
    set_cookie = response.headers.get("set-cookie", "")
    assert "admin_token=" in set_cookie
    assert "Max-Age=0" in set_cookie


def test_protected_admin_html_unauthenticated_redirects_with_next() -> None:
    app = create_app()
    with TestClient(app=app) as client:
        response = client.get(
            "/admin/logs",
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
    assert response.status_code == HTTP_303_SEE_OTHER
    location = response.headers["location"]
    assert location.startswith("/admin/login")
    assert "next=" in location
    assert "%2Fadmin%2Flogs" in location or "/admin/logs" in location


def test_login_after_redirect_round_trip() -> None:
    """Full login → cookie → access protected page round-trip."""
    app = create_app()
    with TestClient(app=app) as client:
        login = client.post(
            "/admin/login",
            data={"token": TOKEN, "next": "/admin/"},
            follow_redirects=False,
        )
        assert login.status_code == HTTP_303_SEE_OTHER
        # TestClient persists cookies. Now navigate to /admin/.
        dashboard = client.get("/admin/")
        assert dashboard.status_code == HTTP_200_OK
