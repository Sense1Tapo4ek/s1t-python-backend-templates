import os
from collections.abc import Iterator

import pytest

from shared.generics import config as generic_config_module


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
    ):
        monkeypatch.delenv(env_var, raising=False)
    yield
    os.environ.pop("SNITCHBOT_DISABLED", None)
