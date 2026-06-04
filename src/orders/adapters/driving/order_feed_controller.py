from litestar import Controller, get
from litestar.channels import ChannelsPlugin
from litestar.response import ServerSentEvent

from ...adapters.driven.listeners import ORDERS_CHANNEL


class OrderFeedController(Controller):
    path = "/orders/feed"
    tags = ["orders (realtime)"]  # noqa: RUF012

    @get("/", summary="Live order feed (SSE)")
    async def feed(self, channels: ChannelsPlugin) -> ServerSentEvent:
        """Stream order-placed events live. `channels` is injected by the plugin."""
        async with channels.start_subscription(ORDERS_CHANNEL) as subscriber:
            return ServerSentEvent(subscriber.iter_events())
