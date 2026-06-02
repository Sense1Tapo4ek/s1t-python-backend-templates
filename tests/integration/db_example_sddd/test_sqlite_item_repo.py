from pathlib import Path
from uuid import uuid4

import aiosqlite
import pytest

from db_example_sddd.adapters.driven.connection import open_connection
from db_example_sddd.domain import Item
from db_example_sddd.ports.driven import SqliteItemRepo

_DDL = Path("migrations/db_example_sddd/001-create-items.sql").read_text()


async def _fresh_conn(tmp_path: Path) -> aiosqlite.Connection:
    conn = await open_connection(tmp_path / "t.db")
    await conn.executescript(_DDL)
    await conn.commit()
    return conn


@pytest.mark.asyncio
async def test_add_get_roundtrip(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    conn = await _fresh_conn(tmp_path)
    repo = SqliteItemRepo(_conn=conn)
    item = Item.create(name="w", description="d", created_at=datetime(2026, 6, 1, tzinfo=UTC))
    await repo.add(item)
    loaded = await repo.get(item.id)
    assert loaded is not None
    assert loaded.id == item.id
    assert loaded.name == "w"
    await conn.close()


@pytest.mark.asyncio
async def test_list_and_delete(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    conn = await _fresh_conn(tmp_path)
    repo = SqliteItemRepo(_conn=conn)
    for i in range(3):
        await repo.add(Item.create(name=f"n{i}", description=None,
                                   created_at=datetime(2026, 6, 1, tzinfo=UTC)))
    rows, total = await repo.list(limit=2, offset=0)
    assert total == 3
    assert len(rows) == 2
    assert await repo.delete(rows[0].id) is True
    assert await repo.get(uuid4()) is None
    await conn.close()
