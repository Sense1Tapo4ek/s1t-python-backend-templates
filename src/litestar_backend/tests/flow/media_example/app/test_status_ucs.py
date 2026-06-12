from datetime import UTC, datetime
from uuid import uuid4

import pytest

from media_example.app import MarkDoneUC, MarkFailedUC, MarkProcessingUC, VideoNotFound
from media_example.domain import Video, VideoStatus

from .conftest import FailingFeed, FakeFeed, FakeUoW, FakeVideoRepo


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
        fake_feed: FakeFeed,
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
        uc = MarkProcessingUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

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
        fake_feed: FakeFeed,
    ) -> None:
        """
        Given no video in the repo,
        When MarkProcessingUC is called with an unknown id,
        Then VideoNotFound is raised and nothing is published to the feed.
        """
        # Arrange
        uc = MarkProcessingUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

        # Act / Assert
        with pytest.raises(VideoNotFound) as exc_info:
            await uc(uuid4())

        assert exc_info.value.video_id is not None
        assert fake_feed.published == []

    @pytest.mark.asyncio
    async def test_publishes_processing_to_feed_after_commit(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
        fake_feed: FakeFeed,
    ) -> None:
        """
        Given a PENDING video,
        When MarkProcessingUC runs,
        Then (video_id, "processing") is published to the feed exactly once.
        """
        # Arrange
        video = _pending_video()
        video.collect_events()
        fake_repo.seed(video)
        uc = MarkProcessingUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

        # Act
        await uc(video.id)

        # Assert
        assert fake_feed.published == [(video.id, "processing")]


class TestBestEffortFeedPublish:
    @pytest.mark.asyncio
    async def test_uc_succeeds_when_feed_raises_port_error(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
        failing_feed: FailingFeed,
    ) -> None:
        """
        Given a PENDING video and a feed that always raises PortError,
        When MarkProcessingUC is called,
        Then the UC does not raise and the video is persisted with PROCESSING status.
        """
        # Arrange
        video = _pending_video()
        video.collect_events()
        fake_repo.seed(video)
        uc = MarkProcessingUC(_repo=fake_repo, _uow=fake_uow, _feed=failing_feed)

        # Act -- must not raise
        await uc(video.id)

        # Assert
        saved = await fake_repo.get_by_id(video.id)
        assert saved is not None
        assert saved.status == VideoStatus.PROCESSING
        assert failing_feed.calls == 1


class TestMarkDoneUC:
    @pytest.mark.asyncio
    async def test_transitions_processing_to_done(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
        fake_feed: FakeFeed,
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
        uc = MarkDoneUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

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
        fake_feed: FakeFeed,
    ) -> None:
        """
        Given no video in the repo,
        When MarkDoneUC is called with an unknown id,
        Then VideoNotFound is raised.
        """
        # Arrange
        uc = MarkDoneUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

        # Act / Assert
        with pytest.raises(VideoNotFound):
            await uc(uuid4())

    @pytest.mark.asyncio
    async def test_publishes_done_to_feed_after_commit(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
        fake_feed: FakeFeed,
    ) -> None:
        """
        Given a PROCESSING video,
        When MarkDoneUC runs,
        Then (video_id, "done") is published to the feed exactly once.
        """
        # Arrange
        video = _pending_video()
        video.collect_events()
        video.mark_processing()
        fake_repo.seed(video)
        uc = MarkDoneUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

        # Act
        await uc(video.id)

        # Assert
        assert fake_feed.published == [(video.id, "done")]


class TestMarkFailedUC:
    @pytest.mark.asyncio
    async def test_transitions_processing_to_failed(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
        fake_feed: FakeFeed,
    ) -> None:
        """
        Given a PROCESSING video in the repo,
        When MarkFailedUC is called,
        Then the video status is FAILED and it is persisted.
        """
        # Arrange
        video = _pending_video()
        video.collect_events()
        video.mark_processing()
        fake_repo.seed(video)
        uc = MarkFailedUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

        # Act
        await uc(video.id)

        # Assert
        saved = await fake_repo.get_by_id(video.id)
        assert saved is not None
        assert saved.status == VideoStatus.FAILED

    @pytest.mark.asyncio
    async def test_raises_not_found_on_missing_id(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
        fake_feed: FakeFeed,
    ) -> None:
        """
        Given no video in the repo,
        When MarkFailedUC is called with an unknown id,
        Then VideoNotFound is raised.
        """
        # Arrange
        uc = MarkFailedUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

        # Act / Assert
        with pytest.raises(VideoNotFound):
            await uc(uuid4())

    @pytest.mark.asyncio
    async def test_publishes_failed_to_feed_after_commit(
        self,
        fake_repo: FakeVideoRepo,
        fake_uow: FakeUoW,
        fake_feed: FakeFeed,
    ) -> None:
        """
        Given a PROCESSING video,
        When MarkFailedUC runs,
        Then (video_id, "failed") is published to the feed exactly once.
        """
        # Arrange
        video = _pending_video()
        video.collect_events()
        video.mark_processing()
        fake_repo.seed(video)
        uc = MarkFailedUC(_repo=fake_repo, _uow=fake_uow, _feed=fake_feed)

        # Act
        await uc(video.id)

        # Assert
        assert fake_feed.published == [(video.id, "failed")]
