from uuid import uuid4

import pytest

from media_processing.app import OnJobFailedUC


class _FakeStore:
    def __init__(self) -> None:
        self.cleared: list = []

    async def add(self, video_id, kind) -> int:
        return 0

    async def clear(self, video_id) -> None:
        self.cleared.append(video_id)


class _FakePublisher:
    def __init__(self) -> None:
        self.failed: list = []

    async def publish_started(self, video_id) -> None: ...
    async def publish_processed(self, video_id) -> None: ...

    async def publish_failed(self, video_id) -> None:
        self.failed.append(video_id)


class TestOnJobFailedUC:
    @pytest.mark.asyncio
    async def test_publishes_failed_and_clears_join(self) -> None:
        """
        Given a video whose job failed terminally,
        When the UC runs,
        Then video_processing_failed is published and the join record cleared.
        """
        # Arrange
        store = _FakeStore()
        publisher = _FakePublisher()
        uc = OnJobFailedUC(_store=store, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id)

        # Assert
        assert publisher.failed == [video_id]
        assert store.cleared == [video_id]
