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
from .feed_limiter import FeedLimiter


async def _event_stream(
    channels: ChannelsPlugin, limiter: FeedLimiter, heartbeat: float
) -> AsyncIterator[SSEData]:
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
        limiter.release()


class VideoFeedController(Controller):
    path = "/videos/feed"
    tags = ["media"]  # noqa: RUF012

    @get("/", summary="Live video feed (SSE)")
    @inject
    async def feed(
        self,
        channels: ChannelsPlugin,
        config: FromDishka[MediaConfig],
        limiter: FromDishka[FeedLimiter],
    ) -> ServerSentEvent:
        if not limiter.try_acquire():
            raise ServiceUnavailableException(detail="feed connection limit reached")
        return ServerSentEvent(_event_stream(channels, limiter, config.feed_heartbeat_seconds))
