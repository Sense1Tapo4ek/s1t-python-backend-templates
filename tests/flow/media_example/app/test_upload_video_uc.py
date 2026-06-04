import pytest

from media_example.app import UploadVideoCommand, UploadVideoUC
from media_example.domain import VideoStatus, VideoUploaded

from .conftest import FakeClock, FakeOutbox, FakeUoW, FakeVideoRepo


class TestUploadVideoUC:
    @pytest.mark.asyncio
    async def test_upload_stores_pending_video(
        self,
        fake_repo: FakeVideoRepo,
        fake_outbox: FakeOutbox,
        fake_uow: FakeUoW,
        fake_clock: FakeClock,
    ) -> None:
        """
        Given a valid source key,
        When UploadVideoUC is called,
        Then a PENDING video is persisted and returned.
        """
        # Arrange
        uc = UploadVideoUC(
            _repo=fake_repo,
            _uow=fake_uow,
            _outbox=fake_outbox,
            _clock=fake_clock,
        )
        command = UploadVideoCommand(source_key="uploads/test.mp4")

        # Act
        video = await uc(command)

        # Assert
        assert video.status == VideoStatus.PENDING
        assert video.source_key == "uploads/test.mp4"
        assert video.uploaded_at == FakeClock.FIXED
        saved = await fake_repo.get_by_id(video.id)
        assert saved is video

    @pytest.mark.asyncio
    async def test_upload_records_one_uploaded_event_in_outbox(
        self,
        fake_repo: FakeVideoRepo,
        fake_outbox: FakeOutbox,
        fake_uow: FakeUoW,
        fake_clock: FakeClock,
    ) -> None:
        """
        Given a valid source key,
        When UploadVideoUC is called,
        Then exactly one VideoUploaded event is added to the outbox.
        """
        # Arrange
        uc = UploadVideoUC(
            _repo=fake_repo,
            _uow=fake_uow,
            _outbox=fake_outbox,
            _clock=fake_clock,
        )
        command = UploadVideoCommand(source_key="uploads/clip.mp4")

        # Act
        video = await uc(command)

        # Assert
        assert len(fake_outbox.added) == 1
        event = fake_outbox.added[0]
        assert isinstance(event, VideoUploaded)
        assert event.video_id == video.id
        assert event.source_key == "uploads/clip.mp4"
        assert event.uploaded_at == FakeClock.FIXED

    @pytest.mark.asyncio
    async def test_upload_uses_unit_of_work(
        self,
        fake_repo: FakeVideoRepo,
        fake_outbox: FakeOutbox,
        fake_uow: FakeUoW,
        fake_clock: FakeClock,
    ) -> None:
        """
        Given a valid source key,
        When UploadVideoUC is called,
        Then the UoW is entered exactly once.
        """
        # Arrange
        uc = UploadVideoUC(
            _repo=fake_repo,
            _uow=fake_uow,
            _outbox=fake_outbox,
            _clock=fake_clock,
        )

        # Act
        await uc(UploadVideoCommand(source_key="uploads/a.mp4"))

        # Assert
        assert fake_uow.entered == 1
        assert fake_uow.exited == 1
