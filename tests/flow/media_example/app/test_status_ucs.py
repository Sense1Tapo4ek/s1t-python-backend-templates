from datetime import UTC, datetime
from uuid import uuid4

import pytest

from media_example.app import MarkDoneUC, MarkProcessingUC, VideoNotFound
from media_example.domain import Video, VideoStatus

from .conftest import FakeUoW, FakeVideoRepo


def _pending_video() -> Video:
    return Video.upload(
        source_key="uploads/sample.mp4",
        uploaded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestMarkProcessingUC:
    @pytest.mark.asyncio
    async def test_transitions_pending_to_processing(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
    ) -> None:
        """
        Given a PENDING video in the repo,
        When MarkProcessingUC is called,
        Then the video status is PROCESSING and it is persisted.
        """
        # Arrange
        video = _pending_video()
        video.collect_events()  # drain upload event
        fake_repo.seed(video)
        uc = MarkProcessingUC(_repo=fake_repo, _uow=fake_uow)

        # Act
        await uc(video.id)

        # Assert
        saved = await fake_repo.get_by_id(video.id)
        assert saved is not None
        assert saved.status == VideoStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_raises_not_found_on_missing_id(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
    ) -> None:
        """
        Given no video in the repo,
        When MarkProcessingUC is called with an unknown id,
        Then VideoNotFound is raised.
        """
        # Arrange
        uc = MarkProcessingUC(_repo=fake_repo, _uow=fake_uow)

        # Act / Assert
        with pytest.raises(VideoNotFound) as exc_info:
            await uc(uuid4())

        assert exc_info.value.video_id is not None


class TestMarkDoneUC:
    @pytest.mark.asyncio
    async def test_transitions_processing_to_done(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
    ) -> None:
        """
        Given a PROCESSING video in the repo,
        When MarkDoneUC is called,
        Then the video status is DONE and it is persisted.
        """
        # Arrange
        video = _pending_video()
        video.collect_events()
        video.mark_processing()
        fake_repo.seed(video)
        uc = MarkDoneUC(_repo=fake_repo, _uow=fake_uow)

        # Act
        await uc(video.id)

        # Assert
        saved = await fake_repo.get_by_id(video.id)
        assert saved is not None
        assert saved.status == VideoStatus.DONE

    @pytest.mark.asyncio
    async def test_raises_not_found_on_missing_id(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
    ) -> None:
        """
        Given no video in the repo,
        When MarkDoneUC is called with an unknown id,
        Then VideoNotFound is raised.
        """
        # Arrange
        uc = MarkDoneUC(_repo=fake_repo, _uow=fake_uow)

        # Act / Assert
        with pytest.raises(VideoNotFound):
            await uc(uuid4())
