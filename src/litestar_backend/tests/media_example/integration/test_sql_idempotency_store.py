from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from media_example.domain import Video, VideoStatus
from media_example.ports.driven.sql_idempotency_store import SqlIdempotencyStore
from shared.adapters.driven.idempotency_sweeper import IdempotencySweeper
from shared.adapters.driven.postgres import build_engine, build_sessionmaker


class _FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _store(session: AsyncSession, *, now: datetime, ttl: int = 3600) -> SqlIdempotencyStore:
    return SqlIdempotencyStore(_session=session, _clock=_FixedClock(now), _ttl_seconds=ttl)


def _video(source_key: str = "s3://bucket/x.mp4") -> Video:
    return Video.upload(source_key=source_key, uploaded_at=datetime(2026, 3, 1, tzinfo=UTC))


@pytest.mark.asyncio
async def test_first_claim_wins_and_second_loses(session: AsyncSession) -> None:
    """
    Given an unclaimed idempotency key,
    When two claims for that key run in the same transaction,
    Then the first returns True and the second returns False.
    """
    # Arrange
    store = _store(session, now=datetime(2026, 3, 1, tzinfo=UTC))
    key = f"k-{uuid4()}"

    # Act
    first = await store.claim(key, fingerprint="fp", video=_video())
    second = await store.claim(key, fingerprint="fp", video=_video())

    # Assert
    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_find_restores_the_video_the_claim_carried(session: AsyncSession) -> None:
    """
    Given a claimed key whose snapshot holds a video,
    When the key is looked up,
    Then every field of the original video comes back unchanged.
    """
    # Arrange
    store = _store(session, now=datetime(2026, 3, 1, tzinfo=UTC))
    key = f"k-{uuid4()}"
    video = Video.upload(
        source_key="s3://bucket/snapshot.mp4",
        uploaded_at=datetime(2026, 3, 1, 12, 30, tzinfo=UTC),
        document={"content_type": "video/mp4", "size": 42},
    )
    await store.claim(key, fingerprint="fp-1", video=video)

    # Act
    stored = await store.find(key)

    # Assert
    assert stored is not None
    assert stored.fingerprint == "fp-1"
    assert stored.video.id == video.id
    assert stored.video.source_key == video.source_key
    assert stored.video.status == VideoStatus.PENDING
    assert stored.video.uploaded_at == video.uploaded_at
    assert stored.video.document == {"content_type": "video/mp4", "size": 42}


@pytest.mark.asyncio
async def test_find_returns_none_for_an_unclaimed_key(session: AsyncSession) -> None:
    """
    Given a key that was never claimed,
    When it is looked up,
    Then None is returned.
    """
    # Act
    stored = await _store(session, now=datetime(2026, 3, 1, tzinfo=UTC)).find(f"k-{uuid4()}")

    # Assert
    assert stored is None


@pytest.mark.asyncio
async def test_sweeper_deletes_only_expired_keys(pg_dsn: str, _migrated: None) -> None:
    """
    Given one expired and one live idempotency key committed to the table,
    When the retention sweep runs,
    Then the expired key is gone and the live one survives.
    """
    # Arrange -- the sweeper opens its own session, so the rows must be committed.
    alchemy_url = pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = build_engine(alchemy_url, "media")
    sessionmaker = build_sessionmaker(engine)
    now = datetime.now(UTC)
    expired_key, live_key = f"k-{uuid4()}", f"k-{uuid4()}"
    try:
        async with sessionmaker() as setup:
            await _store(setup, now=now, ttl=-3600).claim(
                expired_key, fingerprint="fp", video=_video()
            )
            await _store(setup, now=now, ttl=3600).claim(live_key, fingerprint="fp", video=_video())
            await setup.commit()

        # Act
        purged = await IdempotencySweeper(_sessionmaker=sessionmaker).purge_once()

        # Assert
        assert purged >= 1
        async with sessionmaker() as check:
            rows = await check.execute(
                text("SELECT key FROM idempotency_keys WHERE key IN (:a, :b)"),
                {"a": expired_key, "b": live_key},
            )
            assert [r[0] for r in rows] == [live_key]
    finally:
        async with sessionmaker() as cleanup:
            await cleanup.execute(
                text("DELETE FROM idempotency_keys WHERE key IN (:a, :b)"),
                {"a": expired_key, "b": live_key},
            )
            await cleanup.commit()
        await engine.dispose()
