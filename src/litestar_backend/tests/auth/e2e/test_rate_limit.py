from pathlib import Path
from uuid import uuid4

import pytest
import redis
from litestar.status_codes import HTTP_401_UNAUTHORIZED, HTTP_429_TOO_MANY_REQUESTS
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app


def _reset_rate_limit_counters(valkey_url: str) -> None:
    """Earlier e2e tests increment the same Valkey-backed counters (same
    client IP, session-scoped container); start this test from zero."""
    client = redis.Redis.from_url(valkey_url)
    try:
        keys = [k for k in client.scan_iter(match="*rate*limit*")]
        if keys:
            client.delete(*keys)
    finally:
        client.close()


@pytest.fixture(autouse=True)
def _set_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    monkeypatch.setenv("AUTH_JWT_SECRET", "e2e-jwt-secret-please-rotate")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")


def test_login_hammering_hits_429(pg_dsn: str, valkey_url: str) -> None:
    """Given the cap is 3/min, When a 4th login POST arrives, Then 429 --
    while safe methods stay un-throttled."""
    _reset_rate_limit_counters(valkey_url)
    app = create_app()
    creds = {"email": f"rl-{uuid4()}@example.com", "password": "wrong-password xyz"}
    with TestClient(app=app) as client:
        for _ in range(3):
            assert client.post("/auth/login", json=creds).status_code == HTTP_401_UNAUTHORIZED

        throttled = client.post("/auth/login", json=creds)
        assert throttled.status_code == HTTP_429_TOO_MANY_REQUESTS

        # GET endpoints are outside the throttle scope.
        assert client.get("/ping").status_code == 200
