from dataclasses import dataclass, field
from datetime import datetime
from functools import reduce
from uuid import UUID, uuid4

from .errors import EmptyOrder
from .events import OrderPlacedEvent
from .money_vo import Money
from .order_line import OrderLine
from .order_status_vo import OrderStatus


@dataclass(slots=True, kw_only=True)
class Order:
    id: UUID = field(default_factory=uuid4)
    customer_ref: str
    lines: list[OrderLine]
    total: Money
    placed_at: datetime
    status: OrderStatus = OrderStatus.PLACED
    _events: list[object] = field(default_factory=list, repr=False)

    @classmethod
    def place(cls, *, customer_ref: str, lines: list[OrderLine], placed_at: datetime) -> "Order":
        if not lines:
            raise EmptyOrder()
        total = reduce(lambda acc, ln: acc.add(ln.subtotal), lines[1:], lines[0].subtotal)
        order = cls(customer_ref=customer_ref, lines=lines, total=total, placed_at=placed_at)
        order._record(OrderPlacedEvent(order_id=order.id, total=total, placed_at=placed_at))
        return order

    @classmethod
    def reconstitute(
        cls,
        *,
        id: UUID,
        customer_ref: str,
        lines: list[OrderLine],
        total: Money,
        placed_at: datetime,
        status: OrderStatus,
    ) -> "Order":
        return cls(
            id=id, customer_ref=customer_ref, lines=lines, total=total,
            placed_at=placed_at, status=status,
        )

    def _record(self, event: object) -> None:
        self._events.append(event)

    def collect_events(self) -> list[object]:
        events, self._events = self._events[:], []
        return events
