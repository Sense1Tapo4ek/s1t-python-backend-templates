from uuid import uuid4

import pytest

from media_processing.app import CompleteJobUC
from media_processing.domain import JobKind


class _FakeStore:
    def __init__(self, count_after_add: int) -> None:
        self._count = count_after_add
        self.cleared: list = []

    async def add(self, video_id, kind) -> int:
        return self._count

    async def clear(self, video_id) -> None:
        self.cleared.append(video_id)


class TestCompleteJobUC:
    @pytest.mark.asyncio
    async def test_clears_when_join_complete(self) -> None:
        """Given the add brings the count to fan_out, When the UC runs, Then it clears the join."""
        # Arrange
        store = _FakeStore(count_after_add=3)
        uc = CompleteJobUC(_store=store, _fan_out=3)
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
        uc = CompleteJobUC(_store=store, _fan_out=3)

        # Act
        await uc(uuid4(), JobKind.TRANSCODE)

        # Assert
        assert store.cleared == []
