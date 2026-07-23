from pathlib import Path

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app


@pytest.fixture(autouse=True)
def _set_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_use_list_revoke_cycle(pg_dsn: str, valkey_url: str) -> None:
    """Create an api key with admin -> use it as bearer -> list -> revoke -> rejected."""
    app = create_app()
    with TestClient(app=app) as client:
        created = client.post(
            "/auth/api-keys", headers=_bearer(E2E_ADMIN_TOKEN), json={"name": "ci"}
        )
        assert created.status_code == HTTP_201_CREATED
        body = created.json()
        api_key = body["api_key"]
        key_id = body["id"]
        assert api_key.startswith("ak_") and body["name"] == "ci"

        # The minted key authenticates as ADMIN (list requires ADMIN).
        listed = client.get("/auth/api-keys", headers=_bearer(api_key))
        assert listed.status_code == HTTP_200_OK
        assert any(k["id"] == key_id for k in listed.json())

        revoked = client.delete(f"/auth/api-keys/{key_id}", headers=_bearer(E2E_ADMIN_TOKEN))
        assert revoked.status_code == HTTP_204_NO_CONTENT

        # Revoked key no longer authenticates.
        after = client.get("/auth/api-keys", headers=_bearer(api_key))
        assert after.status_code == HTTP_401_UNAUTHORIZED

        # Revoking again is 404 (no active row).
        gone = client.delete(f"/auth/api-keys/{key_id}", headers=_bearer(E2E_ADMIN_TOKEN))
        assert gone.status_code == HTTP_404_NOT_FOUND


def test_create_requires_admin(pg_dsn: str, valkey_url: str) -> None:
    app = create_app()
    with TestClient(app=app) as client:
        resp = client.post("/auth/api-keys", headers=_bearer("not-admin"), json={"name": "x"})
        assert resp.status_code == HTTP_401_UNAUTHORIZED
