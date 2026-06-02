import pytest
from tests.flow.db_example_sddd.conftest import FakeClock, FakeMetrics, FakeRepo

from db_example_sddd.app import ItemManagement, ItemNotFound


@pytest.fixture
def metrics() -> FakeMetrics:
    return FakeMetrics()


@pytest.fixture
def mgmt(metrics: FakeMetrics) -> ItemManagement:
    return ItemManagement(_repo=FakeRepo(), _clock=FakeClock(), _metrics=metrics)


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_persists_and_stamps_created_at(self, mgmt: ItemManagement) -> None:
        item = await mgmt.create(name="w", description=None)
        assert item.created_at == FakeClock().now()
        assert await mgmt._repo.get(item.id) is item

    @pytest.mark.asyncio
    async def test_create_emits_counter_and_histogram(
        self, mgmt: ItemManagement, metrics: FakeMetrics
    ) -> None:
        """
        Given a metrics sink,
        When creating an item,
        Then the created counter increments once and a create-duration is observed.
        """
        await mgmt.create(name="w", description=None)
        assert metrics.increments == [("db_example_items_created_total", 1.0)]
        assert len(metrics.observations) == 1
        assert metrics.observations[0][0] == "db_example_item_create_seconds"


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
