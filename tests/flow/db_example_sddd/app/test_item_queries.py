import pytest
from tests.flow.db_example_sddd.conftest import FakeRepo

from db_example_sddd.app import ItemNotFound, ItemQueries


@pytest.mark.asyncio
async def test_get_missing_raises() -> None:
    from uuid import uuid4

    q = ItemQueries(_repo=FakeRepo())
    with pytest.raises(ItemNotFound):
        await q.get(uuid4())


@pytest.mark.asyncio
async def test_list_returns_items_and_total() -> None:
    from datetime import UTC, datetime

    from db_example_sddd.domain import Item

    repo = FakeRepo()
    for i in range(3):
        await repo.add(Item.create(name=f"n{i}", description=None,
                                   created_at=datetime(2026, 6, 1, tzinfo=UTC)))
    q = ItemQueries(_repo=repo)
    rows, total = await q.list(limit=2, offset=0)
    assert len(rows) == 2
    assert total == 3
