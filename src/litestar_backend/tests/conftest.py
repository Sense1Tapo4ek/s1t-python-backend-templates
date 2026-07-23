import os
from collections.abc import Iterator

import pytest

from shared.generics import config as generic_config_module

_LEVELS = ("unit", "flow", "integration", "e2e")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Tag each test with its pyramid level from the path.

    Layout is `tests/<context>/<level>/...`, so the level is a path segment.
    Marking lets the Taskfile select a level (`pytest -m unit`) without a
    per-level directory to point at, which nested contexts (admin/log) break.
    """
    for item in items:
        path = str(item.path).replace(os.sep, "/")
        for level in _LEVELS:
            if f"/{level}/" in path:
                item.add_marker(getattr(pytest.mark, level))
                break


@pytest.fixture(scope="session")
def pg_dsn() -> Iterator[str]:
    """Session Postgres as an asyncpg DSN.

    If POSTGRES_HOST is already set (compose/CI provides a DB), reuse it and start no
    container. Otherwise start a testcontainers Postgres for the session.
    """
    if os.environ.get("POSTGRES_HOST"):
        user = os.environ.get("POSTGRES_USER", "postgres")
        password = os.environ.get("POSTGRES_PASSWORD", "postgres")
        host = os.environ["POSTGRES_HOST"]
        port = os.environ.get("POSTGRES_PORT", "5432")
        db = os.environ.get("POSTGRES_DB", "litestar_base")
        yield f"postgresql://{user}:{password}@{host}:{port}/{db}"
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:18", dbname="litestar_base") as pg:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        user = pg.username
        password = pg.password
        db = pg.dbname
        # Publish parts so config (PostgresConfig) and the app pick them up.
        os.environ["POSTGRES_HOST"] = host
        os.environ["POSTGRES_PORT"] = str(port)
        os.environ["POSTGRES_USER"] = user
        os.environ["POSTGRES_PASSWORD"] = password
        os.environ["POSTGRES_DB"] = db
        yield f"postgresql://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture(scope="session", autouse=True)
def _pg_env(pg_dsn: str) -> None:
    """Force the session Postgres params into the environment before any test config
    reads them. Depends on pg_dsn so the container is up and POSTGRES_* are exported.
    """
    # pg_dsn already exported POSTGRES_* (container branch) or they were pre-set
    # (compose branch). Nothing else to do; the dependency ordering is the point.
    return


@pytest.fixture(scope="session")
def valkey_url() -> Iterator[str]:
    """Session Valkey URL. Reuse VALKEY_URL if set (compose/CI), else a container."""
    if os.environ.get("VALKEY_URL"):
        yield os.environ["VALKEY_URL"]
        return

    from testcontainers.redis import RedisContainer

    with RedisContainer("valkey/valkey:8") as rc:
        host = rc.get_container_host_ip()
        port = rc.get_exposed_port(6379)
        url = f"redis://{host}:{port}/0"
        os.environ["VALKEY_URL"] = url
        os.environ["VALKEY_HOST"] = host
        os.environ["VALKEY_PORT"] = str(port)
        yield url


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent from the developer's local .env file."""

    monkeypatch.setattr(generic_config_module, "_resolve_env_file", lambda: None)
    monkeypatch.setenv("SNITCHBOT_DISABLED", "1")
    for env_var in (
        "SNITCHBOT_TOKEN",
        "SNITCHBOT_CHAT_ID",
        "APP_NAME",
        "APP_ENV",
        "APP_HOST",
        "APP_PORT",
        "APP_WORKERS",
        "VOLUME_PATH",
        "RUNTIME_PATH",
        "AUTH_ADMIN_TOKEN",
        "PROMETHEUS_MULTIPROC_DIR",
        "METRICS_MULTIPROC_DIR",
        # VALKEY_* are intentionally NOT stripped: create_app() builds the
        # litestar.channels Redis backend at startup, so every full-app e2e
        # test transitively needs a reachable Valkey -- exactly like POSTGRES_*
        # (also kept). The infra layer (compose env / the valkey_url
        # testcontainer fixture) owns these values.
    ):
        monkeypatch.delenv(env_var, raising=False)
    yield
    os.environ.pop("SNITCHBOT_DISABLED", None)


# --- E2E shared fixtures ------------------------------------------------------
# Formerly tests/e2e/conftest.py. With the context-first layout there is no
# single e2e/ directory, so the module-scoped app + client live here at the
# tests root. They are lazy (only built when a test requests them) and the
# rate-limit lift is gated on the `e2e` marker so unit/flow config tests are
# untouched.

E2E_APP_NAME = "test-service"


@pytest.fixture(autouse=True)
def _unthrottled(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lift the rate-limit cap for e2e tests only.

    Rate-limit counters live in the session-scoped Valkey and accumulate
    across e2e tests (same client IP); lift the cap so only the dedicated
    rate-limit test exercises 429. Gated on the `e2e` marker: unit/flow tests
    (including config tests that assert the default cap) never see it.
    """
    if request.node.get_closest_marker("e2e"):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "100000")


@pytest.fixture(scope="module")
def e2e_app(
    tmp_path_factory: pytest.TempPathFactory, pg_dsn: str, valkey_url: str
) -> Iterator[object]:
    """Module-scoped Litestar app with isolated VOLUME_PATH and admin token.

    Uses `pytest.MonkeyPatch` directly -- the function-scoped `monkeypatch`
    fixture is unusable at module scope.
    """
    from _e2e_constants import E2E_ADMIN_TOKEN
    from root.entrypoints.api import create_app

    mp = pytest.MonkeyPatch()
    mp.setenv("APP_NAME", E2E_APP_NAME)
    mp.setenv("VOLUME_PATH", str(tmp_path_factory.mktemp("e2e")))
    mp.setenv("AUTH_ADMIN_TOKEN", E2E_ADMIN_TOKEN)
    mp.setenv("POSTGRES_HOST", os.environ["POSTGRES_HOST"])
    mp.setenv("POSTGRES_PORT", os.environ["POSTGRES_PORT"])
    mp.setenv("POSTGRES_USER", os.environ["POSTGRES_USER"])
    mp.setenv("POSTGRES_PASSWORD", os.environ["POSTGRES_PASSWORD"])
    mp.setenv("POSTGRES_DB", os.environ["POSTGRES_DB"])
    mp.setenv("VALKEY_HOST", os.environ["VALKEY_HOST"])
    mp.setenv("VALKEY_PORT", os.environ["VALKEY_PORT"])
    try:
        yield create_app()
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def e2e_client(e2e_app: object) -> Iterator[object]:
    """Module-scoped TestClient -- lifespan runs ONCE per module.

    Warms up the DI graph by hitting /health so APP-scope dependencies
    (BuildInfoVo, BaseAppConfig) resolve while module-fixture env vars are
    still in place.
    """
    from litestar.testing import TestClient

    with TestClient(app=e2e_app) as client:
        client.get("/health")
        yield client


@pytest.fixture
def e2e_auth_headers() -> dict[str, str]:
    """Bearer header matching the module-scoped admin token."""
    from _e2e_constants import E2E_ADMIN_TOKEN

    return {"Authorization": f"Bearer {E2E_ADMIN_TOKEN}"}
