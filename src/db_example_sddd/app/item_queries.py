from dataclasses import dataclass
from uuid import UUID

from ..domain import Item
from .i_repo import IItemRepo
from .item_management_uc import ItemNotFound


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemQueries:
    _repo: IItemRepo

    async def get(self, item_id: UUID) -> Item:
        item = await self._repo.get(item_id)
        if item is None:
            raise ItemNotFound(item_id)
        return item

    async def list(self, limit: int, offset: int) -> tuple[list[Item], int]:
        return await self._repo.list(limit, offset)
