from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from db_example_sddd.adapters.driven.migrations_runner import apply_migrations
from db_example_sddd.domain import Item
from db_example_sddd.ports.driven.pg_item_repo import PgItemRepo

_SCHEMA = "db_example_sddd"


@pytest_asyncio.fixture(scope="module")
async def _migrated(pg_dsn: str) -> None:
    yoyo_url = pg_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    await apply_migrations(yoyo_url)


@pytest_asyncio.fixture
async def conn(pg_dsn: str, _migrated: None):
    c = await asyncpg.connect(pg_dsn, server_settings={"search_path": _SCHEMA})
    tr = c.transaction()
    await tr.start()
    try:
        yield c
    finally:
        await tr.rollback()
        await c.close()


def _item() -> Item:
    return Item.create(name="widget", description=None, created_at=datetime.now(UTC))


@pytest.mark.asyncio
async def test_add_get_roundtrip(conn) -> None:
    """Given an item, When add then get, Then all fields incl tz-aware created_at match."""
    repo = PgItemRepo(_conn=conn)
    item = _item()
    await repo.add(item)
    loaded = await repo.get(item.id)
    assert loaded is not None
    assert loaded.id == item.id
    assert loaded.name == item.name
    assert loaded.created_at == item.created_at  # tz-aware UTC round-trip


@pytest.mark.asyncio
async def test_list_and_delete(conn) -> None:
    """Given 3 added items, When list paginated then delete, Then counts and removal hold."""
    repo = PgItemRepo(_conn=conn)
    _, baseline = await repo.list(limit=1, offset=0)
    for _ in range(3):
        await repo.add(_item())
    rows, total = await repo.list(limit=2, offset=0)
    assert total == baseline + 3
    assert len(rows) == 2
    victim = rows[0].id
    assert await repo.delete(victim) is True
    assert await repo.delete(uuid4()) is False
