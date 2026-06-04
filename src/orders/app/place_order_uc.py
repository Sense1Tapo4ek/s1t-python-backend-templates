from dataclasses import dataclass

from shared.app import IClock

from ..domain import Order, OrderLine
from .i_event_bus import IEventBus
from .i_order_repo import IOrderRepo
from .i_uow import IUoW


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderCommand:
    customer_ref: str
    lines: list[OrderLine]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderUC:
    _repo: IOrderRepo
    _uow: IUoW
    _event_bus: IEventBus
    _clock: IClock

    async def __call__(self, command: PlaceOrderCommand) -> Order:
        order = Order.place(
            customer_ref=command.customer_ref,
            lines=command.lines,
            placed_at=self._clock.now(),
        )
        async with self._uow:
            await self._repo.save(order)
        # Published AFTER commit: a UoW failure raises above, so no event escapes
        # for a rolled-back order. In-process bus => at-most-once (see spec).
        for event in order.collect_events():
            await self._event_bus.publish(event)
        return order
