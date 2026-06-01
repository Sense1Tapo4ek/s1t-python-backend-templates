from dataclasses import dataclass
from uuid import UUID

import aiosqlite

from shared.generics.errors import PortError

from ....app import IItemRepo
from ....domain import Item
from .item_mappers import to_domain


@dataclass(slots=True, kw_only=True)
class SqliteItemRepo(IItemRepo):
    _conn: aiosqlite.Connection

    async def add(self, item: Item) -> None:
        try:
            await self._conn.execute(
                "INSERT INTO items (id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (str(item.id), item.name, item.description, item.created_at.isoformat()),
            )
            await self._conn.commit()
        except aiosqlite.Error as exc:
            raise PortError(f"insert item failed: {exc}") from exc

    async def get(self, item_id: UUID) -> Item | None:
        cur = await self._conn.execute("SELECT * FROM items WHERE id = ?", (str(item_id),))
        row = await cur.fetchone()
        return to_domain(row) if row else None

    async def list(self, limit: int, offset: int) -> tuple[list[Item], int]:
        cur = await self._conn.execute(
            "SELECT * FROM items ORDER BY created_at LIMIT ? OFFSET ?", (limit, offset)
        )
        rows = await cur.fetchall()
        cur2 = await self._conn.execute("SELECT COUNT(*) AS c FROM items")
        total_row = await cur2.fetchone()
        total = int(total_row["c"]) if total_row else 0
        return [to_domain(r) for r in rows], total

    async def update(self, item: Item) -> None:
        await self._conn.execute(
            "UPDATE items SET name = ?, description = ? WHERE id = ?",
            (item.name, item.description, str(item.id)),
        )
        await self._conn.commit()

    async def delete(self, item_id: UUID) -> bool:
        cur = await self._conn.execute("DELETE FROM items WHERE id = ?", (str(item_id),))
        await self._conn.commit()
        return cur.rowcount > 0
