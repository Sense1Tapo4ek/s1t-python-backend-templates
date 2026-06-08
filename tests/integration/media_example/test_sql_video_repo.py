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
