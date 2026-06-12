from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from shared.generics.errors import PortError

from ..feed import VIDEOS_CHANNEL


class _IChannels(Protocol):
    """Local protocol for litestar's ChannelsPlugin; injected via DI."""

    def publish(self, data: Any, channels: str) -> None: ...


@dataclass(slots=True, kw_only=True)
class ChannelsFeedPublisher:
    _channels: _IChannels

    async def publish(self, video_id: UUID, status: str) -> None:
        try:
            self._channels.publish(
                {"video_id": str(video_id), "status": status},
                VIDEOS_CHANNEL,
            )
        except Exception as exc:
            raise PortError(f"feed publish failed for {video_id}: {exc}") from exc
