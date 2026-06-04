from litestar.channels import ChannelsPlugin
from litestar.events import EventListener, listener

ORDERS_CHANNEL = "orders"


def make_feed_listener(channels: ChannelsPlugin) -> EventListener:
    @listener("order_placed")
    async def feed_order_placed(
        order_id: str, amount: str, currency: str, placed_at: str
    ) -> None:
        channels.publish(
            {"order_id": order_id, "amount": amount, "currency": currency, "placed_at": placed_at},
            ORDERS_CHANNEL,
        )

    return feed_order_placed
