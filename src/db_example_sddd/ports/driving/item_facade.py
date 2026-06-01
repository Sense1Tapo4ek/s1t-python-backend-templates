from dataclasses import dataclass
from uuid import UUID

from ...app import ItemManagement, ItemQueries
from .item_dto import ItemModel, to_model


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemFacade:
    _mgmt: ItemManagement
    _queries: ItemQueries

    async def create(self, name: str, description: str | None = None) -> ItemModel:
        return to_model(await self._mgmt.create(name, description))

    async def get(self, item_id: UUID) -> ItemModel:
        return to_model(await self._queries.get(item_id))

    async def list(self, limit: int, offset: int) -> tuple[list[ItemModel], int]:
        items, total = await self._queries.list(limit, offset)
        return [to_model(i) for i in items], total

    async def update(self, item_id: UUID, name: str | None = None,
                     description: str | None = None) -> ItemModel:
        return to_model(await self._mgmt.update(item_id, name=name, description=description))

    async def delete(self, item_id: UUID) -> None:
        await self._mgmt.delete(item_id)


class PooledItemFacade(ItemFacade):
    """Distinct type so Dishka can bind the pooled wiring."""


class PerRequestItemFacade(ItemFacade):
    """Distinct type so Dishka can bind the per-request wiring."""
