from datetime import UTC, datetime
from uuid import UUID

import pytest

from media_example.app import ListVideosQuery
from media_example.domain import Video, VideoStatus

from .conftest import FakeVideoRepo


def _video(n: int, ts: datetime) -> Video:
    return Video.reconstitute(
        id=UUID(int=n), source_key=f"k{n}", status=VideoStatus.PENDING, uploaded_at=ts
    )


class TestListVideosQuery:
    @pytest.mark.asyncio
    async def test_returns_newest_first(self, fake_repo: FakeVideoRepo) -> None:
        """
        Given videos seeded across two timestamps,
        When the query runs with after=None,
        Then rows come back newest-first.
        """
        fake_repo.seed(_video(1, datetime(2026, 1, 1, tzinfo=UTC)))
        fake_repo.seed(_video(2, datetime(2026, 1, 2, tzinfo=UTC)))
        query = ListVideosQuery(_repo=fake_repo)

        result = await query(None, 50)

        assert [v.id for v in result] == [UUID(int=2), UUID(int=1)]

    @pytest.mark.asyncio
    async def test_after_cursor_excludes_seen(self, fake_repo: FakeVideoRepo) -> None:
        """
        Given a cursor at the newest row,
        When the query runs,
        Then only strictly-older rows return.
        """
        newer = _video(2, datetime(2026, 1, 2, tzinfo=UTC))
        fake_repo.seed(_video(1, datetime(2026, 1, 1, tzinfo=UTC)))
        fake_repo.seed(newer)
        query = ListVideosQuery(_repo=fake_repo)

        result = await query((newer.uploaded_at, newer.id), 50)

        assert [v.id for v in result] == [UUID(int=1)]
