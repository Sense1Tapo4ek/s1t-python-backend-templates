from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from media_example.domain import Video
from media_example.domain.video_status_vo import VideoStatus
from media_example.ports.driven.orm_models import VideoRow
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
    # media.videos is shared with e2e tests that COMMIT rows; a keyset assertion
    # over the whole table needs a known slate. Clearing inside this test's
    # transaction is undone by the session fixture's rollback.
    await session.execute(delete(VideoRow))
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


@pytest.mark.asyncio
async def test_audit_columns_populated_on_save(session: AsyncSession) -> None:
    """
    Given a saved video,
    When the row is read back,
    Then created_at and updated_at are set and deleted_at is NULL.

    The bump of updated_at across UPDATEs is cross-transaction (now() is fixed
    within a transaction); this single-transaction test only asserts the columns
    are populated.
    """
    # Arrange
    repo = SqlVideoRepo(_session=session)
    await session.execute(delete(VideoRow))
    video = Video.upload(source_key="s3://bucket/audit.mp4")

    # Act
    await repo.save(video)
    row = (await session.execute(select(VideoRow).where(VideoRow.id == video.id))).scalar_one()

    # Assert
    assert row.created_at is not None
    assert row.updated_at is not None
    assert row.deleted_at is None


@pytest.mark.asyncio
async def test_soft_delete_hides_row_from_reads(session: AsyncSession) -> None:
    """
    Given a saved video,
    When it is soft-deleted,
    Then get_by_id returns None and it is absent from list_page, but the row
    still exists with deleted_at set.
    """
    # Arrange
    repo = SqlVideoRepo(_session=session)
    await session.execute(delete(VideoRow))
    video = Video.upload(source_key="s3://bucket/sd.mp4")
    await repo.save(video)

    # Act
    deleted = await repo.soft_delete(video.id)

    # Assert
    assert deleted is True
    assert await repo.get_by_id(video.id) is None
    assert await repo.list_page(after=None, limit=50) == []
    row = (await session.execute(select(VideoRow).where(VideoRow.id == video.id))).scalar_one()
    assert row.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_returns_false_for_unknown_id(session: AsyncSession) -> None:
    """Given no matching active row, When soft_delete, Then it returns False."""
    repo = SqlVideoRepo(_session=session)
    video = Video.upload(source_key="s3://bucket/ghost.mp4")

    assert await repo.soft_delete(video.id) is False


@pytest.mark.asyncio
async def test_document_round_trips(session: AsyncSession) -> None:
    """Given a video with a JSONB document, When saved and loaded, Then it round-trips."""
    repo = SqlVideoRepo(_session=session)
    await session.execute(delete(VideoRow))
    doc = {"content_type": "video/mp4", "duration_s": 12, "hd": True}
    video = Video.upload(source_key="s3://bucket/doc.mp4", document=doc)

    await repo.save(video)
    loaded = await repo.get_by_id(video.id)

    assert loaded is not None
    assert loaded.document == doc


@pytest.mark.asyncio
async def test_list_by_content_type_filters_on_jsonb_field(session: AsyncSession) -> None:
    """
    Given videos with different document content types,
    When filtering by content_type via the JSONB ->> extraction,
    Then only matching active videos are returned.
    """
    # Arrange
    repo = SqlVideoRepo(_session=session)
    await session.execute(delete(VideoRow))
    mp4 = Video.upload(source_key="a", document={"content_type": "video/mp4"})
    mp3 = Video.upload(source_key="b", document={"content_type": "audio/mpeg"})
    await repo.save(mp4)
    await repo.save(mp3)

    # Act
    found = await repo.list_by_content_type("video/mp4", limit=50)

    # Assert
    assert [v.id for v in found] == [mp4.id]
