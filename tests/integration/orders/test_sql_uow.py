from datetime import UTC, datetime
from decimal import Decimal

import pytest

from orders.domain import Money, Order, OrderLine
from orders.ports.driven.sql_order_repo import SqlOrderRepo
from shared.adapters.driven.postgres import SqlUoW


def _order() -> Order:
    return Order.place(
        customer_ref="c-1",
        lines=[OrderLine(product_ref="sku-1", quantity=1, unit_price=Money(amount=Decimal("1.00"), currency="USD"))],
        placed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_uow_rolls_back_on_error(conn) -> None:
    """Given a save inside a UoW that raises, When exiting, Then nothing persists."""
    repo = SqlOrderRepo(_conn=conn)
    order = _order()
    with pytest.raises(RuntimeError):
        async with SqlUoW(_conn=conn):
            await repo.save(order)
            raise RuntimeError("boom")
    rows = await conn.fetch("SELECT id FROM orders WHERE id = $1", order.id)
    assert rows == []
