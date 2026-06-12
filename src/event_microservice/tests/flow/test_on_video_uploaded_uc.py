from uuid import uuid4

import pytest

from media_processing.app import OnVideoUploadedUC
from media_processing.domain import JobKind
from shared.generics.errors import PortError


class _SpyQueue:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def enqueue(self, video_id, kind) -> None:
        self.calls.append((video_id, kind))


class _FakePublisher:
    def __init__(self) -> None:
        self.started: list = []
        self.processed: list = []
        self.failed: list = []

    async def publish_started(self, video_id) -> None:
        self.started.append(video_id)

    async def publish_processed(self, video_id) -> None:
        self.processed.append(video_id)

    async def publish_failed(self, video_id) -> None:
        self.failed.append(video_id)


class _FailingPublisher(_FakePublisher):
    """Publisher whose publish_started raises PortError."""

    async def publish_started(self, video_id) -> None:
        raise PortError("valkey unreachable")


class TestOnVideoUploadedUC:
    @pytest.mark.asyncio
    async def test_enqueues_one_job_per_kind(self) -> None:
        """Given a video id, When the UC runs, Then all 3 JobKinds are enqueued once."""
        # Arrange
        queue = _SpyQueue()
        publisher = _FakePublisher()
        uc = OnVideoUploadedUC(_queue=queue, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id)

        # Assert
        assert {kind for _, kind in queue.calls} == set(JobKind)
        assert [vid for vid, _ in queue.calls] == [video_id] * 3

    @pytest.mark.asyncio
    async def test_port_error_from_publish_propagates(self) -> None:
        """
        Given a publisher that raises PortError on publish_started,
        When OnVideoUploadedUC runs,
        Then the PortError propagates to the caller AND all 3 jobs were already
        enqueued (the inbound video_uploaded message stays unacked; on FastStream
        redelivery the jobs are re-enqueued -- the documented design trade-off).
        """
        # Arrange
        queue = _SpyQueue()
        publisher = _FailingPublisher()
        uc = OnVideoUploadedUC(_queue=queue, _publisher=publisher)
        video_id = uuid4()

        # Act / Assert
        with pytest.raises(PortError):
            await uc(video_id)

        assert len(queue.calls) == 3

    @pytest.mark.asyncio
    async def test_publishes_started_after_enqueue(self) -> None:
        """
        Given a queue that accepts all jobs,
        When the UC runs,
        Then video_processing_started is published exactly once, after fan-out.
        """
        # Arrange
        queue = _SpyQueue()
        publisher = _FakePublisher()
        uc = OnVideoUploadedUC(_queue=queue, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id)

        # Assert
        assert publisher.started == [video_id]
        assert len(queue.calls) == 3
