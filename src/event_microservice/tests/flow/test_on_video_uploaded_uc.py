from uuid import uuid4

import pytest

from media_processing.app import OnVideoUploadedUC
from media_processing.domain import JobKind


class _SpyQueue:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def enqueue(self, video_id, kind) -> None:
        self.calls.append((video_id, kind))


class TestOnVideoUploadedUC:
    @pytest.mark.asyncio
    async def test_enqueues_one_job_per_kind(self) -> None:
        """Given a video id, When the UC runs, Then all 3 JobKinds are enqueued once."""
        # Arrange
        queue = _SpyQueue()
        uc = OnVideoUploadedUC(_queue=queue)
        video_id = uuid4()

        # Act
        await uc(video_id)

        # Assert
        assert {kind for _, kind in queue.calls} == set(JobKind)
        assert [vid for vid, _ in queue.calls] == [video_id] * 3
