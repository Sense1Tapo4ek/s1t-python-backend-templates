import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app

E2E_APP_NAME = "test-service"


@pytest.fixture(autouse=True)
def _set_admin_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable auth for the own-app log tests (test_logs_api builds its app
    without setting the token). Formerly in the admin e2e conftest, which the
    log subtree no longer inherits under the context-first layout."""
    monkeypatch.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"}


_SEED_LINES = [
    {
        "timestamp": "2026-05-31T10:00:00Z",
        "level": "info",
        "logger": "root",
        "event": "boot",
        "context": {"pid": 1},
    },
    {
        "timestamp": "2026-05-31T10:00:01Z",
        "level": "warning",
        "logger": "auth",
        "event": "login slow",
        "context": {"ms": 900},
    },
    {
        "timestamp": "2026-05-31T10:00:02Z",
        "level": "error",
        "logger": "auth",
        "event": "login failed",
        "context": {"user": "x"},
    },
]


@pytest.fixture(scope="module")
def e2e_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Litestar]:
    """Module-scoped app with a pre-seeded JSONL log file.

    Overrides the global `e2e_client` fixture for this subtree so the
    file-tail log endpoints have history to read. The default
    `log_file_path` resolves to `<volume>/logs/app.jsonl`; that file is
    written before `create_app()`. The app's own structlog file handler
    targets the same path, so `configure_structlog` is stubbed to keep
    the seed pristine (these tests exercise the read path, not emission).
    """
    mp = pytest.MonkeyPatch()
    volume = tmp_path_factory.mktemp("e2e-log")
    log_dir = volume / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file: Path = log_dir / "app.jsonl"
    log_file.write_text("".join(json.dumps(line) + "\n" for line in _SEED_LINES), encoding="utf-8")

    mp.setenv("APP_NAME", E2E_APP_NAME)
    mp.setenv("VOLUME_PATH", str(volume))
    mp.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    mp.setattr("root.composition.lifespan.configure_structlog", lambda **_: None)
    try:
        yield create_app()
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def e2e_client(e2e_app: Litestar) -> Iterator[TestClient]:
    # Warm DI while the module-fixture env (VOLUME_PATH, AUTH_ADMIN_TOKEN) is
    # still set: the autouse `_isolate_environment` wipes env before each test,
    # but APP-scope Dishka deps (BaseAppConfig, AdminLogConfig, the file reader)
    # cache here and survive. Hitting the log API -- not just /health -- forces
    # AdminLogConfig + the reader to resolve against the seeded VOLUME_PATH.
    headers = {"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"}
    with TestClient(app=e2e_app) as client:
        client.get("/health")
        client.get("/api/v1/admin/logs/", headers=headers)
        yield client
