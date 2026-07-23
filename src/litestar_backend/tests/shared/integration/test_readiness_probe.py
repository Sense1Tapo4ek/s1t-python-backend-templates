import pytest

from shared.adapters.driven.postgres import build_probe_engine
from shared.adapters.driven.readiness import ReadinessProbe
from shared.adapters.driven.valkey import build_valkey_client


@pytest.mark.asyncio
async def test_probe_reports_up_when_infra_reachable(pg_dsn: str, valkey_url: str) -> None:
    """Given reachable Postgres and Valkey, When check(), Then ok with both up."""
    engine = build_probe_engine(pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1))
    valkey = build_valkey_client(valkey_url)
    probe = ReadinessProbe(_engine=engine, _valkey=valkey)
    try:
        report = await probe.check()
    finally:
        await valkey.aclose()
        await engine.dispose()

    assert report.ok is True
    assert report.checks == {"postgres": "up", "valkey": "up"}


@pytest.mark.asyncio
async def test_probe_reports_postgres_down_on_bad_url(valkey_url: str) -> None:
    """Given an unreachable Postgres, When check(), Then not ok and postgres down."""
    engine = build_probe_engine("postgresql+asyncpg://user:pw@127.0.0.1:1/none")
    valkey = build_valkey_client(valkey_url)
    probe = ReadinessProbe(_engine=engine, _valkey=valkey, _timeout_s=1.0)
    try:
        report = await probe.check()
    finally:
        await valkey.aclose()
        await engine.dispose()

    assert report.ok is False
    assert report.checks["postgres"] == "down"
    assert report.checks["valkey"] == "up"
