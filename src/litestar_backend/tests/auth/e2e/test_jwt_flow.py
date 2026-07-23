from pathlib import Path

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
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
    monkeypatch.setenv("AUTH_JWT_SECRET", "e2e-jwt-secret-please-rotate")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_issue_use_refresh_revoke_cycle(valkey_url: str) -> None:
    """Issue with admin token -> use access as bearer -> refresh -> revoke -> rejected."""
    app = create_app()
    with TestClient(app=app) as client:
        issued = client.post("/auth/token", headers=_bearer(E2E_ADMIN_TOKEN))
        assert issued.status_code == HTTP_200_OK
        body = issued.json()
        access, refresh = body["access_token"], body["refresh_token"]
        assert body["token_type"] == "Bearer" and body["expires_in"] == 900

        reissued = client.post("/auth/token", headers=_bearer(access))
        assert reissued.status_code == HTTP_200_OK

        refreshed = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert refreshed.status_code == HTTP_200_OK
        new_refresh = refreshed.json()["refresh_token"]
        assert new_refresh != refresh

        reused = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert reused.status_code == HTTP_401_UNAUTHORIZED

        revoked = client.post("/auth/revoke", json={"token": access})
        assert revoked.status_code == HTTP_204_NO_CONTENT
        after_revoke = client.post("/auth/token", headers=_bearer(access))
        assert after_revoke.status_code == HTTP_401_UNAUTHORIZED


def test_issue_requires_admin_credential() -> None:
    """Without a valid admin credential, /auth/token is 401."""
    app = create_app()
    with TestClient(app=app) as client:
        resp = client.post("/auth/token", headers=_bearer("not-the-admin-token"))
        assert resp.status_code == HTTP_401_UNAUTHORIZED
