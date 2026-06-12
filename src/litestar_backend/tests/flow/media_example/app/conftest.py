from datetime import UTC, datetime
from uuid import UUID

import pytest

from media_example.domain import Video, VideoUploaded


class FakeVideoRepo:
    def __init__(self) -> None:
        self._store: dict[UUID, Video] = {}
        self._order: list[UUID] = []

    async def save(self, video: Video) -> None:
        if video.id not in self._store:
            self._order.append(video.id)
        self._store[video.id] = video

    async def get_by_id(self, video_id: UUID) -> Video | None:
        return self._store.get(video_id)

    async def list_recent(self, limit: int) -> list[Video]:
        ids = list(reversed(self._order))[:limit]
        return [self._store[vid_id] for vid_id in ids]

    def seed(self, video: Video) -> None:
        if video.id not in self._store:
            self._order.append(video.id)
        self._store[video.id] = video


class FakeOutbox:
    def __init__(self) -> None:
        self.added: list[VideoUploaded] = []

    async def add(self, event: VideoUploaded) -> None:
        self.added.append(event)


class FakeUoW:
    def __init__(self) -> None:
        self.entered: int = 0
        self.exited: int = 0

    async def __aenter__(self) -> "FakeUoW":
        self.entered += 1
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.exited += 1


class FakeClock:
    FIXED = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.FIXED


@pytest.fixture
def fake_repo() -> FakeVideoRepo:
    return FakeVideoRepo()


@pytest.fixture
def fake_outbox() -> FakeOutbox:
    return FakeOutbox()


@pytest.fixture
def fake_uow() -> FakeUoW:
    return FakeUoW()


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


class FakeFeed:
    def __init__(self) -> None:
        self.published: list[tuple] = []

    async def publish(self, video_id: UUID, status: str) -> None:
        self.published.append((video_id, status))


@pytest.fixture
def fake_feed() -> FakeFeed:
    return FakeFeed()
