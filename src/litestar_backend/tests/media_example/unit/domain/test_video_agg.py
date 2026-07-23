import pytest

from media_example.domain import Video, VideoStatus
from media_example.domain.errors import EmptySourceKey, InvalidTransition


def test_upload_creates_pending_and_records_event() -> None:
    v = Video.upload(source_key="s3://bucket/a.mp4")
    assert v.status == VideoStatus.PENDING
    assert len(v.collect_events()) == 1


def test_empty_source_key_rejected() -> None:
    with pytest.raises(EmptySourceKey):
        Video.upload(source_key="")


def test_transitions() -> None:
    v = Video.upload(source_key="k")
    v.collect_events()
    v.mark_processing()
    assert v.status == VideoStatus.PROCESSING
    v.mark_done()
    assert v.status == VideoStatus.DONE


def test_done_is_terminal() -> None:
    v = Video.upload(source_key="k")
    v.mark_processing()
    v.mark_done()
    with pytest.raises(InvalidTransition):
        v.mark_processing()


def test_upload_carries_document() -> None:
    v = Video.upload(source_key="k", document={"content_type": "video/mp4"})
    assert v.document == {"content_type": "video/mp4"}


def test_upload_defaults_document_to_empty() -> None:
    v = Video.upload(source_key="k")
    assert v.document == {}
