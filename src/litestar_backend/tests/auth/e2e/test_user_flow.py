from pathlib import Path
from uuid import uuid4

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
)
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app


@pytest.fixture(autouse=True)
def _set_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    monkeypatch.setenv("AUTH_JWT_SECRET", "e2e-jwt-secret-please-rotate")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _creds() -> dict[str, str]:
    return {"email": f"user-{uuid4()}@example.com", "password": "s3cret-pass"}


def test_register_login_me_cycle(pg_dsn: str, valkey_url: str) -> None:
    """Register -> duplicate 409 -> login -> /me carries the user id."""
    app = create_app()
    with TestClient(app=app) as client:
        creds = _creds()
        created = client.post("/auth/register", json=creds)
        assert created.status_code == HTTP_201_CREATED
        body = created.json()
        assert body["email"] == creds["email"] and body["role"] == "user"

        duplicate = client.post("/auth/register", json=creds)
        assert duplicate.status_code == HTTP_409_CONFLICT

        logged = client.post("/auth/login", json=creds)
        assert logged.status_code == HTTP_200_OK
        access = logged.json()["access_token"]

        me = client.get("/auth/me", headers=_bearer(access))
        assert me.status_code == HTTP_200_OK
        assert me.json() == {"subject": body["id"], "role": "user"}


def test_login_rejects_bad_credentials(pg_dsn: str, valkey_url: str) -> None:
    """Unknown email and wrong password both map to one uniform 401."""
    app = create_app()
    with TestClient(app=app) as client:
        creds = _creds()
        assert client.post("/auth/login", json=creds).status_code == HTTP_401_UNAUTHORIZED

        client.post("/auth/register", json=creds)
        wrong = {"email": creds["email"], "password": "not the right password"}
        assert client.post("/auth/login", json=wrong).status_code == HTTP_401_UNAUTHORIZED


def test_admin_lists_and_deactivates_user(pg_dsn: str, valkey_url: str) -> None:
    """Admin pages users (keyset), deactivates one; the user loses login and
    refresh, while a plain user cannot touch the admin surface."""
    app = create_app()
    with TestClient(app=app) as client:
        creds = _creds()
        user_id = client.post("/auth/register", json=creds).json()["id"]
        logged = client.post("/auth/login", json=creds).json()
        access, refresh = logged["access_token"], logged["refresh_token"]

        # A plain user is 403 on the admin surface.
        assert client.get("/auth/users", headers=_bearer(access)).status_code == (
            HTTP_403_FORBIDDEN
        )

        listed = client.get("/auth/users", headers=_bearer(E2E_ADMIN_TOKEN), params={"limit": 1})
        assert listed.status_code == HTTP_200_OK
        page = listed.json()
        assert len(page["items"]) == 1
        assert page["next_cursor"] is None or isinstance(page["next_cursor"], str)

        bad_cursor = client.get(
            "/auth/users", headers=_bearer(E2E_ADMIN_TOKEN), params={"cursor": "garbage"}
        )
        assert bad_cursor.status_code == HTTP_400_BAD_REQUEST

        gone = client.delete(f"/auth/users/{user_id}", headers=_bearer(E2E_ADMIN_TOKEN))
        assert gone.status_code == HTTP_204_NO_CONTENT

        # Deactivation cuts login and the refresh path immediately.
        assert client.post("/auth/login", json=creds).status_code == HTTP_401_UNAUTHORIZED
        refreshed = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert refreshed.status_code == HTTP_401_UNAUTHORIZED
