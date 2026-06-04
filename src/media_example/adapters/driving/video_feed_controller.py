from litestar import Controller, get
from litestar.channels import ChannelsPlugin
from litestar.response import ServerSentEvent

from ...ports.driving import VIDEOS_CHANNEL


class VideoFeedController(Controller):
    path = "/videos/feed"
    tags = ["media"]  # noqa: RUF012

    @get("/", summary="Live video feed (SSE)")
    async def feed(self, channels: ChannelsPlugin) -> ServerSentEvent:
        async with channels.start_subscription(VIDEOS_CHANNEL) as subscriber:
            return ServerSentEvent(subscriber.iter_events())
