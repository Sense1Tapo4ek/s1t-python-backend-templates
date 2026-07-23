import pytest

from shared.config import PostgresConfig


def test_dsn_properties_compose_from_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given POSTGRES_* parts, When reading DSN props, Then each driver URL is correct."""
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "litestar_base")

    cfg = PostgresConfig()

    assert cfg.asyncpg_dsn == "postgresql://u:p@db:5432/litestar_base"
    assert cfg.alchemy_url == "postgresql+asyncpg://u:p@db:5432/litestar_base"
    assert cfg.yoyo_url == "postgresql+psycopg://u:p@db:5432/litestar_base"


def test_defaults_are_localhost_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """Given no env, When constructing, Then sensible localhost defaults apply."""
    for k in (
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        monkeypatch.delenv(k, raising=False)
    cfg = PostgresConfig()
    assert cfg.host == "localhost"
    assert cfg.port == 5432
    assert cfg.db == "litestar_base"
