from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from media_example.domain import Video
from media_example.domain.video_status_vo import VideoStatus
from media_example.ports.driven.sql_video_repo import SqlVideoRepo


@pytest.mark.asyncio
async def test_save_and_get_by_id_roundtrip(session: AsyncSession) -> None:
    """
    Given a new Video built via upload(),
    When saved and fetched by id,
    Then all fields round-trip correctly.
    """
    # Arrange
    video = Video.upload(source_key="s3://bucket/x.mp4")
    repo = SqlVideoRepo(_session=session)

    # Act
    await repo.save(video)
    loaded = await repo.get_by_id(video.id)

    # Assert
    assert loaded is not None
    assert loaded.id == video.id
    assert loaded.source_key == "s3://bucket/x.mp4"
    assert loaded.status == VideoStatus.PENDING
    assert loaded.uploaded_at is not None


@pytest.mark.asyncio
async def test_save_upsert_updates_status(session: AsyncSession) -> None:
    """
    Given a saved PENDING video that is then marked PROCESSING,
    When the updated video is saved again,
    Then fetching by id returns status PROCESSING (upsert updated the row).
    """
    # Arrange
    video = Video.upload(source_key="s3://bucket/y.mp4")
    repo = SqlVideoRepo(_session=session)
    await repo.save(video)

    # Act
    video.mark_processing()
    await repo.save(video)

    # Assert -- locate by id, don't assume empty table
    loaded = await repo.get_by_id(video.id)
    assert loaded is not None
    assert loaded.id == video.id
    assert loaded.status == VideoStatus.PROCESSING


@pytest.mark.asyncio
async def test_list_page_keyset_orders_and_paginates(session: AsyncSession) -> None:
    """
    Given videos including three that share an uploaded_at,
    When paging with list_page(after, limit=2),
    Then rows are newest-first with (uploaded_at, id) as a stable tiebreaker
    and no row is skipped or repeated across pages.
    """
    # Arrange
    repo = SqlVideoRepo(_session=session)
    shared_ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    rows = [
        Video.reconstitute(
            id=UUID(int=i), source_key=f"k{i}", status=VideoStatus.PENDING, uploaded_at=shared_ts
        )
        for i in (1, 2, 3)
    ]
    newer = Video.reconstitute(
        id=UUID(int=99),
        source_key="k99",
        status=VideoStatus.PENDING,
        uploaded_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    for v in (*rows, newer):
        await repo.save(v)

    # Act
    page1 = await repo.list_page(after=None, limit=2)
    cursor = (page1[-1].uploaded_at, page1[-1].id)
    page2 = await repo.list_page(after=cursor, limit=2)

    # Assert
    ids = [v.id for v in (*page1, *page2)]
    assert ids == [UUID(int=99), UUID(int=3), UUID(int=2), UUID(int=1)]
    assert len(set(ids)) == 4
