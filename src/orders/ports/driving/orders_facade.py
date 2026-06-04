from dataclasses import dataclass

from ...app import ListRecentOrdersQuery, PlaceOrderCommand, PlaceOrderUC
from .order_dto import OrderModel, PlaceOrderRequest, to_command_lines, to_model


@dataclass(frozen=True, slots=True, kw_only=True)
class OrdersFacade:
    _place_uc: PlaceOrderUC
    _recent: ListRecentOrdersQuery

    async def place(self, request: PlaceOrderRequest) -> OrderModel:
        command = PlaceOrderCommand(
            customer_ref=request.customer_ref,
            lines=to_command_lines(request.currency, request.lines),
        )
        return to_model(await self._place_uc(command))

    async def list_recent(self, limit: int) -> list[OrderModel]:
        return [to_model(o) for o in await self._recent(limit)]
