from typing import Protocol

from ..domain import Order


class IOrderRepo(Protocol):
    async def save(self, order: Order) -> None: ...
    async def list_recent(self, limit: int) -> list[Order]: ...
