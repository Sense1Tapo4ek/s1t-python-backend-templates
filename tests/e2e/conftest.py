"""Module-scoped E2E app + client.

Each E2E module that opts in by requesting `e2e_client` gets a single
Litestar app and a single TestClient for the whole module — the lifespan
runs once, not once per test. Lifespan boots SQLite, runs migrations,
opens channels, and resolves the DI graph; doing it 50x per file is the
dominant cost of the e2e suite.

Tests that need bespoke env (e.g. GIT_COMMIT_SHA in test_health) keep
their per-test `create_app()` and don't request this fixture.

Note on env timing: the global `tests/conftest.py::_isolate_environment`
fixture is autouse + function-scoped; it deletes APP_NAME before each
test. Module-scoped fixtures run BEFORE that autouse, so we set env and
warm up DI (one HTTP request) inside the e2e_client setup. Dishka caches
APP-scope objects, so the warmed BuildInfoVo etc. survive even after the
autouse fixture deletes the env vars during each test.
"""

from collections.abc import Iterator

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app

E2E_APP_NAME = "test-service"


@pytest.fixture(scope="module")
def e2e_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Litestar]:
    """Module-scoped Litestar app with isolated VOLUME_PATH and admin token.

    Uses `pytest.MonkeyPatch` directly — the function-scoped `monkeypatch`
    fixture is unusable at module scope.
    """
    mp = pytest.MonkeyPatch()
    mp.setenv("APP_NAME", E2E_APP_NAME)
    mp.setenv("VOLUME_PATH", str(tmp_path_factory.mktemp("e2e")))
    mp.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    try:
        yield create_app()
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def e2e_client(e2e_app: Litestar) -> Iterator[TestClient]:
    """Module-scoped TestClient — lifespan runs ONCE per module.

    Warms up the DI graph by hitting /health so APP-scope dependencies
    (BuildInfoVo, BaseAppConfig) resolve while module-fixture env vars
    are still in place. See module docstring.
    """
    with TestClient(app=e2e_app) as client:
        client.get("/health")
        yield client


@pytest.fixture
def e2e_auth_headers() -> dict[str, str]:
    """Bearer header matching the module-scoped admin token."""
    return {"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"}
