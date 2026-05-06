"""Why a separate Protocol from IEventBus: log broadcast is transport,
not domain. The payload is opaque raw structlog JSON; msgspec
round-tripping through `dict` would be wasteful and adds no safety."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from litestar.channels import ChannelsPlugin

from ....app.interfaces import ILogBroadcaster

_LOG_CHANNEL = "log.broadcast"


@dataclass(slots=True, kw_only=True)
class ChannelsLogBroadcaster(ILogBroadcaster):
    _channels: ChannelsPlugin

    async def subscribe(self) -> AsyncGenerator[str, None]:
        async with self._channels.start_subscription(_LOG_CHANNEL) as sub:
            async for raw in sub.iter_events():
                yield raw.decode("utf-8")

    async def broadcast(self, raw_json: str) -> None:
        self._channels.publish(raw_json.encode("utf-8"), _LOG_CHANNEL)

    async def broadcast_batch(self, items: list[str]) -> None:
        if not items:
            return
        # Channels accepts an iterable for batch publish on the same channel,
        # but the API takes a single payload — loop is cheap (in-process).
        for item in items:
            self._channels.publish(item.encode("utf-8"), _LOG_CHANNEL)
