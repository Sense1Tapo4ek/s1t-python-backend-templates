"""Integration tests for VideoStatusConsumer.

Real Postgres (testcontainer via pg_dsn fixture) + real Valkey.
The consumer opens its own committed sessions, so we use a separate
engine/sessionmaker that commits, then clean up explicitly in teardown.
"""

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from media_example.adapters.driving.status_consumer import (
    VIDEO_STATUS_STREAM,
    VideoStatusConsumer,
)
from media_example.app import (
    ListVideosQuery,
    MarkDoneUC,
    MarkFailedUC,
    MarkProcessingUC,
    UploadVideoUC,
)
from media_example.domain import Video, VideoStatus
from media_example.ports.driven.sql_outbox_repo import SqlOutboxRepo
from media_example.ports.driven.sql_video_repo import SqlVideoRepo
from media_example.ports.driving import MediaFacade
from shared.adapters.driven.clocks import SystemClock
from shared.adapters.driven.postgres import SqlUoW, build_engine, build_sessionmaker
from shared.adapters.driven.valkey import build_valkey_client
from shared.generics.errors import PortError

_SCHEMA = "media"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def committed_sm(
    pg_dsn: str, _migrated: None
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A sessionmaker whose sessions COMMIT (unlike the rolled-back `session`
    fixture). Needed because the consumer opens its own sessions internally."""
    alchemy_url = pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = build_engine(alchemy_url, _SCHEMA)
    sm = build_sessionmaker(engine)
    yield sm
    await engine.dispose()


@pytest_asyncio.fixture
async def valkey_clean(valkey_url: str) -> AsyncIterator[aioredis.Redis]:
    """Valkey client that deletes the video_status stream before and after each test."""
    client: aioredis.Redis = build_valkey_client(valkey_url)
    await client.delete(VIDEO_STATUS_STREAM)
    try:
        yield client
    finally:
        await client.delete(VIDEO_STATUS_STREAM)
        await client.aclose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload(video_id: UUID, event_type: str) -> str:
    """Build a wire-format payload string for the video_status stream."""
    return json.dumps(
        {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "video_id": str(video_id),
            "occurred_at": datetime.now(UTC).isoformat(),
            "version": 1,
        }
    )


def _entry(video_id: UUID, event_type: str) -> dict[str, bytes | str]:
    """Build the stream field dict (payload key only) for XADD."""
    return {"payload": _payload(video_id, event_type)}


class _RecordingFeed:
    """Fake IFeedPublisher that records (video_id, status) calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str]] = []

    async def publish(self, video_id: UUID, status: str) -> None:
        self.calls.append((video_id, status))


async def _seed_video(
    sm: async_sessionmaker[AsyncSession],
    *,
    video_id: UUID,
    status: VideoStatus = VideoStatus.PENDING,
) -> None:
    """Insert a video row in the given status (committed)."""
    video = Video.reconstitute(
        id=video_id,
        source_key=f"s3://bucket/{video_id}.mp4",
        status=status,
        uploaded_at=datetime.now(UTC),
    )
    async with sm() as session:
        repo = SqlVideoRepo(_session=session)
        uow = SqlUoW(_session=session)
        async with uow:
            await repo.save(video)


async def _load_status(sm: async_sessionmaker[AsyncSession], video_id: UUID) -> VideoStatus:
    """Load a video's current status via a fresh session."""
    async with sm() as session:
        repo = SqlVideoRepo(_session=session)
        video = await repo.get_by_id(video_id)
        assert video is not None
        return video.status


async def _delete_video(sm: async_sessionmaker[AsyncSession], video_id: UUID) -> None:
    """Hard-delete a video row (cleanup)."""
    async with sm() as session, session.begin():
        await session.execute(text("DELETE FROM media.videos WHERE id = :id"), {"id": video_id})


def _make_facade_factory(feed: _RecordingFeed) -> Callable[[AsyncSession], MediaFacade]:
    """Return a callable(session) -> MediaFacade using the recording feed."""
    clock = SystemClock()

    def factory(session: AsyncSession) -> MediaFacade:
        repo = SqlVideoRepo(_session=session)
        outbox = SqlOutboxRepo(_session=session)
        uow = SqlUoW(_session=session)
        return MediaFacade(
            _upload=UploadVideoUC(_repo=repo, _uow=uow, _outbox=outbox, _clock=clock),
            _recent=ListVideosQuery(_repo=repo),
            _mark_processing=MarkProcessingUC(_repo=repo, _uow=uow, _feed=feed),
            _mark_done=MarkDoneUC(_repo=repo, _uow=uow, _feed=feed),
            _mark_failed=MarkFailedUC(_repo=repo, _uow=uow, _feed=feed),
        )

    return factory


def _make_failing_factory() -> Callable[[AsyncSession], MediaFacade]:
    """Return a factory whose every facade call raises PortError.

    Simplest construction: the factory itself raises PortError rather than
    building a facade with a broken repo, because the consumer calls the
    factory inside the session block and the propagation path is identical.
    This tests that _handle does NOT ack on PortError and re-raises.
    """

    def factory(session: AsyncSession) -> MediaFacade:
        raise PortError("injected transient failure")

    return factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_started_then_processed_drives_video_to_done(
    committed_sm: async_sessionmaker[AsyncSession],
    valkey_clean: aioredis.Redis,
    _migrated: None,
) -> None:
    """
    Given a PENDING video and two status events (started, processed) on the stream,
    When drain_once() processes both,
    Then the video is DONE, the feed recorded the transitions in order,
    and no entries remain pending in the consumer group.
    """
    # Arrange
    video_id = uuid4()
    feed = _RecordingFeed()
    factory = _make_facade_factory(feed)
    consumer = VideoStatusConsumer(
        _valkey=valkey_clean,
        _sessionmaker=committed_sm,
        _facade_factory=factory,
        _batch=10,
        _block_ms=200,
    )
    await _seed_video(committed_sm, video_id=video_id)
    await valkey_clean.xadd(VIDEO_STATUS_STREAM, _entry(video_id, "video_processing_started"))
    await valkey_clean.xadd(VIDEO_STATUS_STREAM, _entry(video_id, "video_processed"))

    try:
        # Act
        await consumer.ensure_group()
        handled = await consumer.drain_once()

        # Assert: both events consumed
        assert handled == 2

        # Assert: video reached DONE
        status = await _load_status(committed_sm, video_id)
        assert status == VideoStatus.DONE

        # Assert: feed saw both transitions in order
        statuses = [s for (_vid, s) in feed.calls]
        assert statuses == ["processing", "done"]

        # Assert: nothing pending
        pending_info = await valkey_clean.xpending(VIDEO_STATUS_STREAM, "media_example")
        assert pending_info["pending"] == 0
    finally:
        await _delete_video(committed_sm, video_id)


@pytest.mark.asyncio
async def test_duplicate_event_is_acked_and_skipped(
    committed_sm: async_sessionmaker[AsyncSession],
    valkey_clean: aioredis.Redis,
    _migrated: None,
) -> None:
    """
    Given a video already in PROCESSING and a duplicate started event,
    When drain_once() runs,
    Then handled == 1, feed is untouched (InvalidTransition absorbed), pending == 0.
    """
    # Arrange
    video_id = uuid4()
    feed = _RecordingFeed()
    factory = _make_facade_factory(feed)
    consumer = VideoStatusConsumer(
        _valkey=valkey_clean,
        _sessionmaker=committed_sm,
        _facade_factory=factory,
        _batch=10,
        _block_ms=200,
    )
    await _seed_video(committed_sm, video_id=video_id, status=VideoStatus.PROCESSING)
    await valkey_clean.xadd(VIDEO_STATUS_STREAM, _entry(video_id, "video_processing_started"))

    try:
        # Act
        await consumer.ensure_group()
        handled = await consumer.drain_once()

        # Assert
        assert handled == 1
        assert feed.calls == []

        pending_info = await valkey_clean.xpending(VIDEO_STATUS_STREAM, "media_example")
        assert pending_info["pending"] == 0
    finally:
        await _delete_video(committed_sm, video_id)


@pytest.mark.asyncio
async def test_malformed_payload_is_acked_and_dropped(
    committed_sm: async_sessionmaker[AsyncSession],
    valkey_clean: aioredis.Redis,
    _migrated: None,
) -> None:
    """
    Given a stream entry with a non-JSON payload,
    When drain_once() runs,
    Then handled == 1 and nothing remains pending (poison pill acked).
    """
    # Arrange
    feed = _RecordingFeed()
    factory = _make_facade_factory(feed)
    consumer = VideoStatusConsumer(
        _valkey=valkey_clean,
        _sessionmaker=committed_sm,
        _facade_factory=factory,
        _batch=10,
        _block_ms=200,
    )
    await valkey_clean.xadd(VIDEO_STATUS_STREAM, {"payload": b"not json"})

    # Act
    await consumer.ensure_group()
    handled = await consumer.drain_once()

    # Assert
    assert handled == 1
    pending_info = await valkey_clean.xpending(VIDEO_STATUS_STREAM, "media_example")
    assert pending_info["pending"] == 0


@pytest.mark.asyncio
async def test_failed_event_marks_video_failed(
    committed_sm: async_sessionmaker[AsyncSession],
    valkey_clean: aioredis.Redis,
    _migrated: None,
) -> None:
    """
    Given a video in PROCESSING and a video_processing_failed event,
    When drain_once() runs,
    Then video status is FAILED, feed recorded ("failed",), pending == 0.
    """
    # Arrange
    video_id = uuid4()
    feed = _RecordingFeed()
    factory = _make_facade_factory(feed)
    consumer = VideoStatusConsumer(
        _valkey=valkey_clean,
        _sessionmaker=committed_sm,
        _facade_factory=factory,
        _batch=10,
        _block_ms=200,
    )
    await _seed_video(committed_sm, video_id=video_id, status=VideoStatus.PROCESSING)
    await valkey_clean.xadd(VIDEO_STATUS_STREAM, _entry(video_id, "video_processing_failed"))

    try:
        # Act
        await consumer.ensure_group()
        handled = await consumer.drain_once()

        # Assert
        assert handled == 1

        status = await _load_status(committed_sm, video_id)
        assert status == VideoStatus.FAILED

        statuses = [s for (_vid, s) in feed.calls]
        assert statuses == ["failed"]

        pending_info = await valkey_clean.xpending(VIDEO_STATUS_STREAM, "media_example")
        assert pending_info["pending"] == 0
    finally:
        await _delete_video(committed_sm, video_id)


@pytest.mark.asyncio
async def test_port_error_entry_stays_pending_then_recovers(
    committed_sm: async_sessionmaker[AsyncSession],
    valkey_clean: aioredis.Redis,
    _migrated: None,
) -> None:
    """
    Given a PENDING video and a started event,
    When consumer_a (broken factory) processes the event and raises PortError,
    Then the entry stays pending (not acked).

    When consumer_b (healthy factory, _claim_idle_ms=0) runs drain_once(),
    Then it claims the stale entry via XAUTOCLAIM, applies it successfully,
    and the video transitions to PROCESSING with pending == 0.
    """
    # Arrange
    video_id = uuid4()
    feed = _RecordingFeed()

    await _seed_video(committed_sm, video_id=video_id)
    await valkey_clean.xadd(VIDEO_STATUS_STREAM, _entry(video_id, "video_processing_started"))

    consumer_a = VideoStatusConsumer(
        _valkey=valkey_clean,
        _sessionmaker=committed_sm,
        _facade_factory=_make_failing_factory(),
        _batch=10,
        _block_ms=200,
    )

    try:
        # Act: consumer_a fails -- PortError propagates out of drain_once
        await consumer_a.ensure_group()
        with pytest.raises(PortError):
            await consumer_a.drain_once()

        # Assert: entry is still pending under consumer_a's name
        pending_info = await valkey_clean.xpending(VIDEO_STATUS_STREAM, "media_example")
        assert pending_info["pending"] == 1

        # Act: consumer_b reclaims immediately (claim_idle_ms=0) and applies
        consumer_b = VideoStatusConsumer(
            _valkey=valkey_clean,
            _sessionmaker=committed_sm,
            _facade_factory=_make_facade_factory(feed),
            _batch=10,
            _block_ms=200,
            _claim_idle_ms=0,
        )
        # consumer_b reuses the group created by consumer_a; ensure_group tolerates BUSYGROUP
        await consumer_b.ensure_group()
        handled = await consumer_b.drain_once()

        # Assert: claimed entry was processed
        assert handled >= 1

        status = await _load_status(committed_sm, video_id)
        assert status == VideoStatus.PROCESSING

        pending_info = await valkey_clean.xpending(VIDEO_STATUS_STREAM, "media_example")
        assert pending_info["pending"] == 0
    finally:
        await _delete_video(committed_sm, video_id)
