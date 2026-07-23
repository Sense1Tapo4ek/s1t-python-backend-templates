from uuid import uuid4

import pytest

from media_processing.app import CompleteJobUC
from media_processing.domain import JobKind
from shared.generics.errors import PortError


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []


class _FakeStore:
    def __init__(self, count_after_add: int, recorder: _Recorder | None = None) -> None:
        self._count = count_after_add
        self.cleared: list = []
        self._recorder = recorder

    async def add(self, video_id, kind) -> int:
        return self._count

    async def clear(self, video_id) -> None:
        self.cleared.append(video_id)
        if self._recorder is not None:
            self._recorder.calls.append("clear")


class _FakePublisher:
    def __init__(self, recorder: _Recorder | None = None) -> None:
        self.started: list = []
        self.processed: list = []
        self.failed: list = []
        self._recorder = recorder

    async def publish_started(self, video_id) -> None:
        self.started.append(video_id)

    async def publish_processed(self, video_id) -> None:
        self.processed.append(video_id)
        if self._recorder is not None:
            self._recorder.calls.append("publish")

    async def publish_failed(self, video_id) -> None:
        self.failed.append(video_id)


class _FailingPublisher(_FakePublisher):
    """Publisher whose publish_processed raises PortError."""

    async def publish_processed(self, video_id) -> None:
        raise PortError("valkey unreachable")


class TestCompleteJobUC:
    @pytest.mark.asyncio
    async def test_clears_when_join_complete(self) -> None:
        """Given the add brings the count to fan_out, When the UC runs, Then it clears the join."""
        # Arrange
        store = _FakeStore(count_after_add=3)
        publisher = _FakePublisher()
        uc = CompleteJobUC(_store=store, _fan_out=3, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id, JobKind.STT)

        # Assert
        assert store.cleared == [video_id]

    @pytest.mark.asyncio
    async def test_does_not_clear_when_incomplete(self) -> None:
        """Given the add leaves the count below fan_out, When the UC runs, Then it does NOT clear."""
        # Arrange
        store = _FakeStore(count_after_add=2)
        publisher = _FakePublisher()
        uc = CompleteJobUC(_store=store, _fan_out=3, _publisher=publisher)

        # Act
        await uc(uuid4(), JobKind.TRANSCODE)

        # Assert
        assert store.cleared == []

    @pytest.mark.asyncio
    async def test_publishes_processed_when_join_complete(self) -> None:
        """
        Given all jobs are done (count == fan_out),
        When the UC runs,
        Then video_processed is published and the join record cleared.
        """
        # Arrange
        store = _FakeStore(count_after_add=3)
        publisher = _FakePublisher()
        uc = CompleteJobUC(_store=store, _fan_out=3, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id, JobKind.STT)

        # Assert
        assert publisher.processed == [video_id]
        assert store.cleared == [video_id]

    @pytest.mark.asyncio
    async def test_does_not_publish_when_incomplete(self) -> None:
        """
        Given the join is not yet complete (count < fan_out),
        When the UC runs,
        Then video_processed is NOT published and nothing is cleared.
        """
        # Arrange
        store = _FakeStore(count_after_add=2)
        publisher = _FakePublisher()
        uc = CompleteJobUC(_store=store, _fan_out=3, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id, JobKind.TRANSCODE)

        # Assert
        assert publisher.processed == []
        assert store.cleared == []

    @pytest.mark.asyncio
    async def test_port_error_from_publish_propagates(self) -> None:
        """
        Given a publisher that raises PortError on publish_processed,
        When CompleteJobUC runs with a complete join (count == fan_out),
        Then the PortError propagates to the caller AND the join is NOT cleared
        (the SAQ job fails and retries, finding the join intact).
        """
        # Arrange
        store = _FakeStore(count_after_add=3)
        publisher = _FailingPublisher()
        uc = CompleteJobUC(_store=store, _fan_out=3, _publisher=publisher)
        video_id = uuid4()

        # Act / Assert
        with pytest.raises(PortError):
            await uc(video_id, JobKind.STT)

        assert store.cleared == []

    @pytest.mark.asyncio
    async def test_publish_before_clear_order(self) -> None:
        """
        Given all jobs are done (count == fan_out),
        When the UC runs,
        Then publish_processed is called before clear (at-least-once guarantee).
        """
        # Arrange
        recorder = _Recorder()
        store = _FakeStore(count_after_add=3, recorder=recorder)
        publisher = _FakePublisher(recorder=recorder)
        uc = CompleteJobUC(_store=store, _fan_out=3, _publisher=publisher)
        video_id = uuid4()

        # Act
        await uc(video_id, JobKind.STT)

        # Assert
        assert recorder.calls == ["publish", "clear"]
