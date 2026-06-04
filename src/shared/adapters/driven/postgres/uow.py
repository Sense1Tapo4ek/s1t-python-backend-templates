from dataclasses import dataclass, field

import asyncpg

from shared.generics.errors import PortError


@dataclass(slots=True, kw_only=True)
class SqlUoW:
    """asyncpg-transaction unit of work, shared across contexts.

    Concrete, not inheriting any context's `IUoW` Protocol: it satisfies them
    structurally (`__aenter__`/`__aexit__`), so each context maps it to its own
    `IUoW` in its provider without `shared` importing a bounded context.
    Commits on clean exit, rolls back on exception; wraps asyncpg failures in
    `PortError`.
    """

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
