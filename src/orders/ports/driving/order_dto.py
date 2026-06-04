from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import msgspec
from litestar.dto import MsgspecDTO

from ...domain import Money, Order, OrderLine


class OrderLineModel(msgspec.Struct, kw_only=True):
    product_ref: Annotated[str, msgspec.Meta(min_length=1, examples=["sku-1"])]
    quantity: Annotated[int, msgspec.Meta(ge=1, examples=[2])]
    # `ge` is unsupported on Decimal by msgspec's DTO inspection; the domain
    # Money VO rejects negative amounts (NegativeMoney) at construction.
    unit_price: Annotated[Decimal, msgspec.Meta(examples=["5.00"])]


class OrderModel(msgspec.Struct, kw_only=True):
    id: Annotated[UUID, msgspec.Meta(description="Server-assigned id.")]
    customer_ref: Annotated[str, msgspec.Meta(min_length=1, examples=["c-1"])]
    currency: Annotated[str, msgspec.Meta(min_length=3, max_length=3, examples=["USD"])]
    lines: list[OrderLineModel]
    total: Annotated[Decimal, msgspec.Meta(description="Sum of line subtotals (server-computed).")]
    status: Annotated[str, msgspec.Meta(examples=["placed"])]
    placed_at: Annotated[datetime, msgspec.Meta(description="UTC placement timestamp.")]


class PlaceOrderRequest(msgspec.Struct, kw_only=True):
    customer_ref: Annotated[str, msgspec.Meta(min_length=1, examples=["c-1"])]
    currency: Annotated[str, msgspec.Meta(min_length=3, max_length=3, examples=["USD"])]
    # No boundary min_length: an empty order is a domain rule (EmptyOrder ->
    # 409), demonstrating domain validation rather than a 400 schema reject.
    lines: list[OrderLineModel]


OrderReadDTO = MsgspecDTO[OrderModel]


def to_model(order: Order) -> OrderModel:
    return OrderModel(
        id=order.id,
        customer_ref=order.customer_ref,
        currency=order.total.currency,
        lines=[
            OrderLineModel(product_ref=ln.product_ref, quantity=ln.quantity, unit_price=ln.unit_price.amount)
            for ln in order.lines
        ],
        total=order.total.amount,
        status=order.status.value,
        placed_at=order.placed_at,
    )


def to_command_lines(currency: str, lines: list[OrderLineModel]) -> list[OrderLine]:
    return [
        OrderLine(
            product_ref=m.product_ref,
            quantity=m.quantity,
            unit_price=Money(amount=m.unit_price, currency=currency),
        )
        for m in lines
    ]
