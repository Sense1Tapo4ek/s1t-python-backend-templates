import asyncpg

from ...domain import Money, Order, OrderLine, OrderStatus


def line_to_domain(row: asyncpg.Record, currency: str) -> OrderLine:
    return OrderLine(
        product_ref=row["product_ref"],
        quantity=row["quantity"],
        unit_price=Money(amount=row["unit_price"], currency=currency),
    )


def order_to_domain(order_row: asyncpg.Record, line_rows: list[asyncpg.Record]) -> Order:
    currency = order_row["currency"]
    return Order.reconstitute(
        id=order_row["id"],
        customer_ref=order_row["customer_ref"],
        lines=[line_to_domain(r, currency) for r in line_rows],
        total=Money(amount=order_row["total"], currency=currency),
        placed_at=order_row["placed_at"],
        status=OrderStatus(order_row["status"]),
    )
