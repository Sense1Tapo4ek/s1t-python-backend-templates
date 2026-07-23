import pytest
from prometheus_client import Histogram
from sqlalchemy import text

from shared.adapters.driven.postgres import DB_QUERY_DURATION, build_engine


def _hist_count(hist: Histogram) -> float:
    for metric in hist.collect():
        for sample in metric.samples:
            if sample.name.endswith("_count"):
                return sample.value
    return 0.0


@pytest.mark.asyncio
async def test_query_is_timed_into_histogram(pg_dsn: str) -> None:
    """
    Given an observed engine,
    When a statement executes,
    Then the db_query_duration_seconds histogram count increases.
    """
    # Arrange
    alchemy_url = pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    before = _hist_count(DB_QUERY_DURATION)
    engine = build_engine(alchemy_url, "public")

    # Act
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await engine.dispose()

    # Assert
    assert _hist_count(DB_QUERY_DURATION) > before
