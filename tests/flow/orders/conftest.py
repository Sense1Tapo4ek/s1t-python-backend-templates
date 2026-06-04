from datetime import UTC, datetime
from uuid import UUID

from orders.app import IEventBus, IOrderRepo, IUoW
from orders.domain import Order


class FakeClock:
    def now(self) -> datetime:
        return datetime(2026, 6, 4, tzinfo=UTC)


class FakeUoW(IUoW):
    def __init__(self) -> None:
        self.entered = False
        self.committed = False

    async def __aenter__(self) -> "FakeUoW":
        self.entered = True
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self.committed = True


class FakeRepo(IOrderRepo):
    def __init__(self) -> None:
        self.saved: dict[UUID, Order] = {}

    async def save(self, order: Order) -> None:
        self.saved[order.id] = order

    async def list_recent(self, limit: int) -> list[Order]:
        return list(self.saved.values())[:limit]


class RecordingEventBus(IEventBus):
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)
