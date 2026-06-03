from dataclasses import dataclass
from uuid import UUID

import asyncpg

from shared.generics.errors import PortError

from ...app import IItemRepo
from ...domain import Item
from .item_mappers import to_domain


@dataclass(slots=True, kw_only=True)
class PgItemRepo(IItemRepo):
    _conn: asyncpg.Connection

    async def add(self, item: Item) -> None:
        try:
            await self._conn.execute(
                "INSERT INTO items (id, name, description, created_at) VALUES ($1, $2, $3, $4)",
                item.id, item.name, item.description, item.created_at,
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"insert item failed: {exc}") from exc

    async def get(self, item_id: UUID) -> Item | None:
        try:
            row = await self._conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
        except asyncpg.PostgresError as exc:
            raise PortError(f"get item failed: {exc}") from exc
        return to_domain(row) if row else None

    async def list(self, limit: int, offset: int) -> tuple[list[Item], int]:
        try:
            rows = await self._conn.fetch(
                "SELECT * FROM items ORDER BY created_at LIMIT $1 OFFSET $2", limit, offset
            )
            total = await self._conn.fetchval("SELECT COUNT(*) FROM items")
        except asyncpg.PostgresError as exc:
            raise PortError(f"list items failed: {exc}") from exc
        return [to_domain(r) for r in rows], int(total)

    async def update(self, item: Item) -> None:
        try:
            await self._conn.execute(
                "UPDATE items SET name = $1, description = $2 WHERE id = $3",
                item.name, item.description, item.id,
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"update item failed: {exc}") from exc

    async def delete(self, item_id: UUID) -> bool:
        try:
            deleted = await self._conn.fetchval(
                "DELETE FROM items WHERE id = $1 RETURNING id", item_id
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"delete item failed: {exc}") from exc
        return deleted is not None
