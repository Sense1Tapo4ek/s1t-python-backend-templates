from datetime import UTC, datetime
from uuid import UUID

from db_example_sddd.app import IItemRepo, IMetrics
from db_example_sddd.domain import Item


class FakeClock:
    def __init__(self, value: datetime | None = None) -> None:
        self._value = value or datetime(2026, 6, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._value


class FakeRepo(IItemRepo):
    def __init__(self) -> None:
        self.items: dict[UUID, Item] = {}

    async def add(self, item: Item) -> None:
        self.items[item.id] = item

    async def get(self, item_id: UUID) -> Item | None:
        return self.items.get(item_id)

    async def list(self, limit: int, offset: int) -> tuple[list[Item], int]:
        rows = list(self.items.values())
        return rows[offset : offset + limit], len(rows)

    async def update(self, item: Item) -> None:
        self.items[item.id] = item

    async def delete(self, item_id: UUID) -> bool:
        return self.items.pop(item_id, None) is not None


class FakeMetrics(IMetrics):
    def __init__(self) -> None:
        self.increments: list[tuple[str, float]] = []
        self.observations: list[tuple[str, float]] = []

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        self.increments.append((name, value))

    def observe(self, name: str, value: float, **labels: str) -> None:
        self.observations.append((name, value))
