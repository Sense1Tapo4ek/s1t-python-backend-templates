from datetime import UTC, datetime

import pytest

from db_example_sddd.domain import EmptyItemName, Item


def _ts() -> datetime:
    return datetime(2026, 6, 1, tzinfo=UTC)


class TestItemCreate:
    def test_create_assigns_id_and_fields(self) -> None:
        """Given valid input, When create, Then id is set and fields stored."""
        item = Item.create(name="widget", description="d", created_at=_ts())
        assert item.id is not None
        assert item.name == "widget"
        assert item.description == "d"
        assert item.created_at == _ts()

    def test_create_rejects_empty_name(self) -> None:
        """Given blank name, When create, Then EmptyItemName."""
        with pytest.raises(EmptyItemName):
            Item.create(name="  ", description=None, created_at=_ts())


class TestItemUpdate:
    def test_update_applies_only_given_fields(self) -> None:
        """Given an item, When update(name only), Then description unchanged."""
        item = Item.create(name="a", description="keep", created_at=_ts())
        item.update(name="b")
        assert item.name == "b"
        assert item.description == "keep"

    def test_update_rejects_empty_name(self) -> None:
        item = Item.create(name="a", description=None, created_at=_ts())
        with pytest.raises(EmptyItemName):
            item.update(name="")
