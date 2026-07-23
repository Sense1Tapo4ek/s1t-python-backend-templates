from uuid import UUID

from factories.media import VideoFactory
from media_example.domain import Video, VideoStatus


def test_builds_valid_pending_video() -> None:
    video = VideoFactory.build()
    assert isinstance(video, Video)
    assert isinstance(video.id, UUID)
    assert video.status == VideoStatus.PENDING
    assert video.document == {}
    assert video.collect_events() == []
    assert video.uploaded_at.tzinfo is not None


def test_batch_builds_distinct_videos() -> None:
    videos = VideoFactory.batch(size=5)
    assert len(videos) == 5
    assert len({v.id for v in videos}) == 5


def test_call_site_override() -> None:
    video = VideoFactory.build(source_key="fixed-key")
    assert video.source_key == "fixed-key"
