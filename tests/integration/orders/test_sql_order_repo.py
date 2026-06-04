from datetime import UTC, datetime
from decimal import Decimal

import pytest

from orders.domain import Money, Order, OrderLine
from orders.ports.driven.sql_order_repo import SqlOrderRepo


def _order() -> Order:
    return Order.place(
        customer_ref="c-1",
        lines=[OrderLine(product_ref="sku-1", quantity=2, unit_price=Money(amount=Decimal("5.00"), currency="USD"))],
        placed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_save_and_list_recent_roundtrip(conn) -> None:
    """Given an order with lines, When saved, Then list_recent returns it with lines + total."""
    repo = SqlOrderRepo(_conn=conn)
    order = _order()
    await repo.save(order)
    recent = await repo.list_recent(10)
    assert len(recent) == 1
    loaded = recent[0]
    assert loaded.id == order.id
    assert loaded.total == Money(amount=Decimal("10.00"), currency="USD")
    assert len(loaded.lines) == 1
    assert loaded.lines[0].product_ref == "sku-1"
