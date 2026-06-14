from datetime import UTC, datetime, timedelta
from random import randint

from polyfactory import Use
from polyfactory.factories import DataclassFactory

from media_example.domain import Video, VideoStatus
from media_example.ports.driven.sql_video_repo import SqlVideoRepo


def _recent_ts() -> datetime:
    # tz-aware (the column is TIMESTAMPTZ) and varied, so seeded rows get a
    # realistic spread for keyset paging.
    return datetime.now(tz=UTC) - timedelta(seconds=randint(0, 100_000))


class VideoFactory(DataclassFactory[Video]):
    # PENDING + empty events/document; id, source_key auto-generated.
    status = VideoStatus.PENDING
    document = Use(dict)
    _events = Use(list)
    uploaded_at = Use(_recent_ts)


async def seed_videos(repo: SqlVideoRepo, count: int) -> list[Video]:
    """Build `count` random videos and persist them via `repo`. Returns them."""
    videos = VideoFactory.batch(size=count)
    for video in videos:
        await repo.save(video)
    return videos
