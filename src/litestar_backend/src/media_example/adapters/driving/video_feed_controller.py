import asyncio
from collections.abc import AsyncIterator

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.channels import ChannelsPlugin
from litestar.exceptions import ServiceUnavailableException
from litestar.response import ServerSentEvent, ServerSentEventMessage
from litestar.types import SSEData

from ...config import MediaConfig
from ...ports.driving import VIDEOS_CHANNEL

# Module-level counter is safe: handlers run on one event loop per worker;
# the cap is per-process, which is the resource actually being protected.
_active_feeds = 0


async def _event_stream(channels: ChannelsPlugin, heartbeat: float) -> AsyncIterator[SSEData]:
    global _active_feeds
    try:
        async with channels.start_subscription(VIDEOS_CHANNEL) as subscriber:
            events = subscriber.iter_events()
            while True:
                try:
                    yield await asyncio.wait_for(anext(events), timeout=heartbeat)
                except TimeoutError:
                    # Keep-alive comment: lets proxies and clients detect a
                    # dead connection instead of holding it open forever.
                    yield ServerSentEventMessage(comment="keep-alive")
                except StopAsyncIteration:
                    return
    finally:
        _active_feeds -= 1


class VideoFeedController(Controller):
    path = "/videos/feed"
    tags = ["media"]  # noqa: RUF012

    @get("/", summary="Live video feed (SSE)")
    @inject
    async def feed(
        self, channels: ChannelsPlugin, config: FromDishka[MediaConfig]
    ) -> ServerSentEvent:
        global _active_feeds
        if _active_feeds >= config.feed_max_connections:
            raise ServiceUnavailableException(detail="feed connection limit reached")
        _active_feeds += 1
        return ServerSentEvent(_event_stream(channels, config.feed_heartbeat_seconds))
