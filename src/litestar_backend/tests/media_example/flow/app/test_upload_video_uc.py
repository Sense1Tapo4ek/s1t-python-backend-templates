import pytest
from structlog.testing import capture_logs

from media_example.app import IdempotencyKeyReused, UploadVideoCommand, UploadVideoUC
from media_example.domain import VideoStatus, VideoUploaded

from .conftest import FakeClock, FakeIdempotencyStore, FakeOutbox, FakeUoW, FakeVideoRepo


@pytest.fixture
def uc(
    fake_repo: FakeVideoRepo,
    fake_outbox: FakeOutbox,
    fake_uow: FakeUoW,
    fake_clock: FakeClock,
    fake_idempotency: FakeIdempotencyStore,
) -> UploadVideoUC:
    return UploadVideoUC(
        _repo=fake_repo,
        _uow=fake_uow,
        _outbox=fake_outbox,
        _clock=fake_clock,
        _idempotency=fake_idempotency,
    )


class TestUploadVideoUC:
    @pytest.mark.asyncio
    async def test_upload_stores_pending_video(
        self, uc: UploadVideoUC, fake_repo: FakeVideoRepo
    ) -> None:
        """
        Given a valid source key,
        When UploadVideoUC is called,
        Then a PENDING video is persisted and returned.
        """
        # Arrange
        command = UploadVideoCommand(source_key="uploads/test.mp4")

        # Act
        result = await uc(command)

        # Assert
        assert result.replayed is False
        assert result.video.status == VideoStatus.PENDING
        assert result.video.source_key == "uploads/test.mp4"
        assert result.video.uploaded_at == FakeClock.FIXED
        saved = await fake_repo.get_by_id(result.video.id)
        assert saved is result.video

    @pytest.mark.asyncio
    async def test_upload_records_one_uploaded_event_in_outbox(
        self, uc: UploadVideoUC, fake_outbox: FakeOutbox
    ) -> None:
        """
        Given a valid source key,
        When UploadVideoUC is called,
        Then exactly one VideoUploaded event is added to the outbox.
        """
        # Arrange
        command = UploadVideoCommand(source_key="uploads/clip.mp4")

        # Act
        result = await uc(command)

        # Assert
        assert len(fake_outbox.added) == 1
        event = fake_outbox.added[0]
        assert isinstance(event, VideoUploaded)
        assert event.video_id == result.video.id
        assert event.source_key == "uploads/clip.mp4"
        assert event.uploaded_at == FakeClock.FIXED

    @pytest.mark.asyncio
    async def test_upload_uses_unit_of_work(self, uc: UploadVideoUC, fake_uow: FakeUoW) -> None:
        """
        Given a valid source key,
        When UploadVideoUC is called,
        Then the UoW is entered exactly once.
        """
        # Act
        await uc(UploadVideoCommand(source_key="uploads/a.mp4"))

        # Assert
        assert fake_uow.entered == 1
        assert fake_uow.exited == 1

    @pytest.mark.asyncio
    async def test_upload_emits_app_layer_registered_line(self, uc: UploadVideoUC) -> None:
        """
        Given a valid source key,
        When UploadVideoUC is called,
        Then it emits a "video registered" app-layer line carrying video_id
        (the backend edge of the cross-service video_id correlation chain).
        """
        # Act
        with capture_logs() as logs:
            result = await uc(UploadVideoCommand(source_key="uploads/log.mp4"))

        # Assert
        registered = next(log for log in logs if log["event"] == "video registered")
        assert registered["layer"] == "app"
        assert registered["video_id"] == str(result.video.id)

    @pytest.mark.asyncio
    async def test_no_idempotency_key_never_touches_the_store(
        self, uc: UploadVideoUC, fake_idempotency: FakeIdempotencyStore
    ) -> None:
        """
        Given a command without an idempotency key,
        When UploadVideoUC is called twice with the same payload,
        Then no claim is attempted and two distinct videos are created.
        """
        # Arrange
        command = UploadVideoCommand(source_key="uploads/twice.mp4")

        # Act
        first = await uc(command)
        second = await uc(command)

        # Assert
        assert fake_idempotency.claims == 0
        assert first.video.id != second.video.id

    @pytest.mark.asyncio
    async def test_same_key_and_payload_replays_the_first_video(
        self, uc: UploadVideoUC, fake_repo: FakeVideoRepo, fake_outbox: FakeOutbox
    ) -> None:
        """
        Given an upload already committed under an idempotency key,
        When the identical request is retried with the same key,
        Then the first video is returned as a replay and nothing new is written.
        """
        # Arrange
        command = UploadVideoCommand(source_key="uploads/retry.mp4", idempotency_key="k-1")
        first = await uc(command)

        # Act
        second = await uc(command)

        # Assert
        assert second.replayed is True
        assert second.video.id == first.video.id
        assert second.video.status == first.video.status
        assert second.video.uploaded_at == first.video.uploaded_at
        assert len(fake_outbox.added) == 1
        assert len(await fake_repo.list_page(None, 50)) == 1

    @pytest.mark.asyncio
    async def test_replay_survives_a_reordered_document(self, uc: UploadVideoUC) -> None:
        """
        Given an upload committed with a multi-key document,
        When it is retried with the same keys serialised in a different order,
        Then it still replays -- key order is not part of the payload identity.
        """
        # Arrange
        first = await uc(
            UploadVideoCommand(
                source_key="uploads/doc.mp4",
                document={"a": 1, "b": {"x": 1, "y": 2}},
                idempotency_key="k-doc",
            )
        )

        # Act
        second = await uc(
            UploadVideoCommand(
                source_key="uploads/doc.mp4",
                document={"b": {"y": 2, "x": 1}, "a": 1},
                idempotency_key="k-doc",
            )
        )

        # Assert
        assert second.replayed is True
        assert second.video.id == first.video.id

    @pytest.mark.asyncio
    async def test_same_key_with_a_different_payload_is_rejected(self, uc: UploadVideoUC) -> None:
        """
        Given an upload already committed under an idempotency key,
        When a DIFFERENT payload is sent with that same key,
        Then IdempotencyKeyReused is raised instead of replaying the wrong result.
        """
        # Arrange
        await uc(UploadVideoCommand(source_key="uploads/first.mp4", idempotency_key="k-2"))

        # Act / Assert
        with pytest.raises(IdempotencyKeyReused):
            await uc(UploadVideoCommand(source_key="uploads/other.mp4", idempotency_key="k-2"))
