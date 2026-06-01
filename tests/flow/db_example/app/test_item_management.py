import pytest
from tests.flow.db_example.conftest import FakeClock, FakeRepo

from db_example.app import ItemManagement, ItemNotFound


@pytest.fixture
def mgmt() -> ItemManagement:
    return ItemManagement(_repo=FakeRepo(), _clock=FakeClock())


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_persists_and_stamps_created_at(self, mgmt: ItemManagement) -> None:
        item = await mgmt.create(name="w", description=None)
        assert item.created_at == FakeClock().now()
        assert await mgmt._repo.get(item.id) is item


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_missing_raises(self, mgmt: ItemManagement) -> None:
        from uuid import uuid4

        with pytest.raises(ItemNotFound):
            await mgmt.update(uuid4(), name="x")

    @pytest.mark.asyncio
    async def test_update_partial(self, mgmt: ItemManagement) -> None:
        item = await mgmt.create(name="a", description="keep")
        updated = await mgmt.update(item.id, name="b")
        assert updated.name == "b"
        assert updated.description == "keep"


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_missing_raises(self, mgmt: ItemManagement) -> None:
        from uuid import uuid4

        with pytest.raises(ItemNotFound):
            await mgmt.delete(uuid4())
