from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from media_processing.app import OnVideoUploadedUC
from media_processing.ports.driven import ValkeyInboxStore


class _SpyQueue:
    def __init__(self) -> None:
        self.calls: list = []

    async def enqueue(self, video_id, kind) -> None:
        self.calls.append((video_id, kind))


class _FakePublisher:
    def __init__(self) -> None:
        self.started: list = []

    async def publish_started(self, video_id) -> None:
        self.started.append(video_id)

    async def publish_processed(self, video_id) -> None: ...
    async def publish_failed(self, video_id) -> None: ...


@pytest_asyncio.fixture
async def valkey(valkey_url: str):
    client = aioredis.from_url(valkey_url, decode_responses=True)
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_redelivery_fans_out_once(valkey) -> None:
    """
    Given an uploaded event processed once,
    When the SAME event_id is delivered again (at-least-once redelivery),
    Then the inbox skips it -- jobs fan out once and started publishes once.
    """
    # Arrange
    inbox = ValkeyInboxStore(_valkey=valkey, _ttl_seconds=60)
    queue = _SpyQueue()
    publisher = _FakePublisher()
    uc = OnVideoUploadedUC(_queue=queue, _publisher=publisher, _inbox=inbox)
    video_id, event_id = uuid4(), uuid4()

    # Act
    await uc(video_id, event_id)
    await uc(video_id, event_id)  # redelivery of the same event

    # Assert
    assert len(queue.calls) == 3
    assert publisher.started == [video_id]
