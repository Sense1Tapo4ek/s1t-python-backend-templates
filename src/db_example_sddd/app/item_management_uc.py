import time
from dataclasses import dataclass
from uuid import UUID

from shared.app import IClock
from shared.generics.errors import AppError

from ..domain import Item
from .i_metrics import IMetrics
from .i_repo import IItemRepo


class ItemNotFound(AppError):
    def __init__(self, item_id: UUID) -> None:
        self.item_id = item_id
        super().__init__(f"item {item_id} not found")


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemManagement:
    _repo: IItemRepo
    _clock: IClock
    _metrics: IMetrics

    async def create(self, name: str, description: str | None) -> Item:
        start = time.perf_counter()
        item = Item.create(name=name, description=description, created_at=self._clock.now())
        await self._repo.add(item)
        # Emitted only on success: a repo error raises before this, so the
        # counter and the latency histogram cover successful creates only.
        self._metrics.increment("db_example_items_created_total")
        self._metrics.observe("db_example_item_create_seconds", time.perf_counter() - start)
        return item

    async def update(self, item_id: UUID, name: str | None = None,
                     description: str | None = None) -> Item:
        item = await self._repo.get(item_id)
        if item is None:
            raise ItemNotFound(item_id)
        item.update(name=name, description=description)
        await self._repo.update(item)
        return item

    async def delete(self, item_id: UUID) -> None:
        if not await self._repo.delete(item_id):
            raise ItemNotFound(item_id)
