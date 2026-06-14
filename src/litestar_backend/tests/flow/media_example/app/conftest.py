from datetime import UTC, datetime
from uuid import UUID

import pytest

from media_example.domain import Video, VideoUploaded


class FakeVideoRepo:
    def __init__(self) -> None:
        self._store: dict[UUID, Video] = {}
        self._order: list[UUID] = []
        self._deleted: set[UUID] = set()

    async def save(self, video: Video) -> None:
        if video.id not in self._store:
            self._order.append(video.id)
        self._store[video.id] = video

    async def get_by_id(self, video_id: UUID) -> Video | None:
        if video_id in self._deleted:
            return None
        return self._store.get(video_id)

    async def list_page(self, after: tuple[datetime, UUID] | None, limit: int) -> list[Video]:
        ordered = sorted(
            (v for v in self._store.values() if v.id not in self._deleted),
            key=lambda v: (v.uploaded_at, v.id),
            reverse=True,
        )
        if after is not None:
            ordered = [v for v in ordered if (v.uploaded_at, v.id) < after]
        return ordered[:limit]

    async def soft_delete(self, video_id: UUID) -> bool:
        if video_id in self._store and video_id not in self._deleted:
            self._deleted.add(video_id)
            return True
        return False

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


class FailingFeed:
    """Feed whose publish always raises PortError; used to verify best-effort."""

    def __init__(self) -> None:
        self.calls: int = 0

    async def publish(self, video_id: UUID, status: str) -> None:
        self.calls += 1
        from shared.generics.errors import PortError

        raise PortError("channel unavailable")


@pytest.fixture
def fake_feed() -> FakeFeed:
    return FakeFeed()


@pytest.fixture
def failing_feed() -> FailingFeed:
    return FailingFeed()
