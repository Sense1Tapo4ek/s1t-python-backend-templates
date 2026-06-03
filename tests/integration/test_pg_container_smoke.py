import asyncpg
import pytest


@pytest.mark.asyncio
async def test_container_accepts_connections(pg_dsn: str) -> None:
    """Given the session Postgres, When connecting, Then SELECT 1 returns 1."""
    conn = await asyncpg.connect(pg_dsn)
    try:
        assert await conn.fetchval("SELECT 1") == 1
    finally:
        await conn.close()
