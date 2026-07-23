from typing import Any
from uuid import uuid4

import pytest

from media_example.ports.driven import ChannelsFeedPublisher


class _RecordingChannels:
    def __init__(self) -> None:
        self.published: list[tuple[Any, str]] = []

    def publish(self, data: Any, channels: str) -> None:
        self.published.append((data, channels))


class _FailingChannels:
    def __init__(self) -> None:
        self.calls: int = 0

    def publish(self, data: Any, channels: str) -> None:
        self.calls += 1
        raise RuntimeError("channel plugin not running")


class TestChannelsFeedPublisher:
    @pytest.mark.asyncio
    async def test_publishes_status_payload(self) -> None:
        """
        Given a working channels backend,
        When publish is called,
        Then the status payload is fanned out on the videos channel.
        """
        # Arrange
        channels = _RecordingChannels()
        publisher = ChannelsFeedPublisher(_channels=channels)
        video_id = uuid4()

        # Act
        await publisher.publish(video_id, "processing")

        # Assert
        assert channels.published == [
            ({"video_id": str(video_id), "status": "processing"}, "videos")
        ]

    @pytest.mark.asyncio
    async def test_swallows_infra_failure(self) -> None:
        """
        Given a channels backend that raises on publish,
        When publish is called,
        Then no exception escapes -- best-effort by IFeedPublisher contract.
        """
        # Arrange
        channels = _FailingChannels()
        publisher = ChannelsFeedPublisher(_channels=channels)

        # Act -- must not raise
        await publisher.publish(uuid4(), "done")

        # Assert
        assert channels.calls == 1
