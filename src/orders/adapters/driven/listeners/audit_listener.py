import structlog
from litestar.events import listener
from prometheus_client import Counter

_log = structlog.get_logger("orders.events")
orders_placed_total = Counter("orders_placed_total", "Orders successfully placed")


@listener("order_placed")
async def audit_order_placed(
    order_id: str, amount: str, currency: str, placed_at: str
) -> None:
    orders_placed_total.inc()
    _log.info("order placed", order_id=order_id, amount=amount, currency=currency)
