from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from orders.domain import Money, OrderPlacedEvent
from orders.ports.driven.litestar_event_bus import LitestarEventBus


class _SpyEmitter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def emit(self, event_id: str, /, **kwargs: object) -> None:
        self.calls.append((event_id, kwargs))


@pytest.mark.asyncio
async def test_publish_maps_order_placed_to_emit_with_primitives() -> None:
    """Given OrderPlacedEvent, When published, Then emitter.emit gets primitive kwargs."""
    emitter = _SpyEmitter()
    bus = LitestarEventBus(_emitter=emitter)
    oid = uuid4()
    await bus.publish(
        OrderPlacedEvent(order_id=oid, total=Money(amount=Decimal("15.00"), currency="USD"),
                         placed_at=datetime(2026, 6, 4, tzinfo=UTC))
    )
    assert len(emitter.calls) == 1
    name, kwargs = emitter.calls[0]
    assert name == "order_placed"
    assert kwargs == {
        "order_id": str(oid), "amount": "15.00", "currency": "USD",
        "placed_at": "2026-06-04T00:00:00+00:00",
    }
