from uuid import uuid4

import pytest

from media_processing.app import OnJobFailedUC
from shared.generics.errors import PortError


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []


class _FakeStore:
    def __init__(self, recorder: _Recorder | None = None) -> None:
        self.cleared: list = []
        self._recorder = recorder

    async def add(self, video_id, kind) -> int:
        return 0

    async def clear(self, video_id) -> None:
        self.cleared.append(video_id)
        if self._recorder is not None:
            self._recorder.calls.append("clear")


class _FakePublisher:
    def __init__(self, recorder: _Recorder | None = None) -> None:
        self.failed: list = []
        self._recorder = recorder

    async def publish_started(self, video_id) -> None: ...
    async def publish_processed(self, video_id) -> None: ...

    async def publish_failed(self, video_id) -> None:
        self.failed.append(video_id)
        if self._recorder is not None:
            self._recorder.calls.append("publish")


class _FakePublisherRaises:
    """Publisher whose publish_failed always raises PortError."""

    async def publish_started(self, video_id) -> None: ...
    async def publish_processed(self, video_id) -> None: ...

    async def publish_failed(self, video_id) -> None:
        raise PortError("stream unavailable")


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

    @pytest.mark.asyncio
    async def test_publish_before_clear_order(self) -> None:
        """
        Given a video whose job failed terminally,
        When the UC runs successfully,
        Then publish_failed is called before clear (at-most-once guarantee).
        """
        # Arrange
        recorder = _Recorder()
        store = _FakeStore(recorder=recorder)
        publisher = _FakePublisher(recorder=recorder)
        uc = OnJobFailedUC(_store=store, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id)

        # Assert
        assert recorder.calls == ["publish", "clear"]

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_block_clear(self) -> None:
        """
        Given a video whose job failed terminally and the publisher raises PortError,
        When the UC runs,
        Then the UC does NOT raise and the join record is still cleared.
        """
        # Arrange
        store = _FakeStore()
        publisher = _FakePublisherRaises()
        uc = OnJobFailedUC(_store=store, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id)  # must not raise

        # Assert
        assert store.cleared == [video_id]
