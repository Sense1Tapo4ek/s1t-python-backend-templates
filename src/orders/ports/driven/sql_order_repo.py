from dataclasses import dataclass
from uuid import UUID

import asyncpg

from shared.generics.errors import PortError

from ...app import IOrderRepo
from ...domain import Order
from .order_mappers import order_to_domain


@dataclass(slots=True, kw_only=True)
class SqlOrderRepo(IOrderRepo):
    _conn: asyncpg.Connection

    async def save(self, order: Order) -> None:
        # Caller wraps this in a UoW transaction; the two inserts commit atomically.
        try:
            await self._conn.execute(
                "INSERT INTO orders (id, customer_ref, currency, total, status, placed_at)"
                " VALUES ($1, $2, $3, $4, $5, $6)",
                order.id, order.customer_ref, order.total.currency,
                order.total.amount, order.status.value, order.placed_at,
            )
            await self._conn.executemany(
                "INSERT INTO order_lines (order_id, product_ref, quantity, unit_price)"
                " VALUES ($1, $2, $3, $4)",
                [(order.id, ln.product_ref, ln.quantity, ln.unit_price.amount) for ln in order.lines],
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"save order failed: {exc}") from exc

    async def list_recent(self, limit: int) -> list[Order]:
        try:
            order_rows = await self._conn.fetch(
                "SELECT * FROM orders ORDER BY placed_at DESC LIMIT $1", limit
            )
            if not order_rows:
                return []
            ids = [r["id"] for r in order_rows]
            line_rows = await self._conn.fetch(
                "SELECT * FROM order_lines WHERE order_id = ANY($1::uuid[])", ids
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"list recent orders failed: {exc}") from exc
        by_order: dict[UUID, list[asyncpg.Record]] = {}
        for lr in line_rows:
            by_order.setdefault(lr["order_id"], []).append(lr)
        return [order_to_domain(o, by_order.get(o["id"], [])) for o in order_rows]
