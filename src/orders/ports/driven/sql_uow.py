from dataclasses import dataclass, field

import asyncpg

from shared.generics.errors import PortError

from ...app import IUoW


@dataclass(slots=True, kw_only=True)
class SqlUoW(IUoW):
    _conn: asyncpg.Connection
    _tx: asyncpg.transaction.Transaction | None = field(default=None)

    async def __aenter__(self) -> "SqlUoW":
        self._tx = self._conn.transaction()
        await self._tx.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._tx is None:
            return
        try:
            if exc_type is not None:
                await self._tx.rollback()
            else:
                await self._tx.commit()
        except asyncpg.PostgresError as pg_exc:
            raise PortError(f"uow finalize failed: {pg_exc}") from pg_exc
