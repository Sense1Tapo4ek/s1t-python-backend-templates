from datetime import UTC, datetime
from decimal import Decimal

import pytest

from orders.domain import EmptyOrder, Money, Order, OrderLine, OrderPlacedEvent, OrderStatus


def _line(qty: int = 2) -> OrderLine:
    return OrderLine(product_ref="sku-1", quantity=qty, unit_price=Money(amount=Decimal("5.00"), currency="USD"))


def _ts() -> datetime:
    return datetime(2026, 6, 4, tzinfo=UTC)


class TestOrderPlace:
    def test_place_computes_total_and_records_event(self) -> None:
        """Given lines, When place, Then total = sum(subtotals), status PLACED, one event."""
        order = Order.place(customer_ref="c-1", lines=[_line(2), _line(1)], placed_at=_ts())
        assert order.total == Money(amount=Decimal("15.00"), currency="USD")
        assert order.status is OrderStatus.PLACED
        events = order.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], OrderPlacedEvent)
        assert events[0].order_id == order.id
        assert events[0].total == order.total

    def test_collect_events_drains(self) -> None:
        order = Order.place(customer_ref="c-1", lines=[_line()], placed_at=_ts())
        order.collect_events()
        assert order.collect_events() == []

    def test_place_rejects_empty_lines(self) -> None:
        with pytest.raises(EmptyOrder):
            Order.place(customer_ref="c-1", lines=[], placed_at=_ts())
