import pytest

from media_example.app import DeleteVideoUC, VideoNotFound
from media_example.domain import Video

from .conftest import FakeUoW, FakeVideoRepo


class TestDeleteVideoUC:
    @pytest.mark.asyncio
    async def test_soft_deletes_existing_video(
        self, fake_repo: FakeVideoRepo, fake_uow: FakeUoW
    ) -> None:
        """
        Given a stored video,
        When DeleteVideoUC runs,
        Then it is soft-deleted and reads no longer return it.
        """
        video = Video.upload(source_key="s3://bucket/d.mp4")
        fake_repo.seed(video)
        uc = DeleteVideoUC(_repo=fake_repo, _uow=fake_uow)

        await uc(video.id)

        assert await fake_repo.get_by_id(video.id) is None
        assert fake_uow.entered == 1

    @pytest.mark.asyncio
    async def test_unknown_video_raises_not_found(
        self, fake_repo: FakeVideoRepo, fake_uow: FakeUoW
    ) -> None:
        """
        Given no such video,
        When DeleteVideoUC runs,
        Then VideoNotFound is raised.
        """
        uc = DeleteVideoUC(_repo=fake_repo, _uow=fake_uow)

        with pytest.raises(VideoNotFound):
            await uc(Video.upload(source_key="x").id)
