from dataclasses import dataclass

from ..domain import Order
from .interfaces import IOrderRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ListRecentOrdersQuery:
    _repo: IOrderRepo

    async def __call__(self, limit: int) -> list[Order]:
        return await self._repo.list_recent(limit)
