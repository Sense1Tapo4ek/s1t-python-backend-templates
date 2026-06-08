from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.generics.errors import PortError


@dataclass(slots=True, kw_only=True)
class SqlUoW:
    """SQLAlchemy-session unit of work, shared across contexts.

    Concrete, not inheriting any context's `IUoW` Protocol: it satisfies them
    structurally (`__aenter__`/`__aexit__`), so each context maps it to its own
    `IUoW` in its provider without `shared` importing a bounded context.
    Commits on clean exit, rolls back on exception; wraps SQLAlchemy failures in
    `PortError`. The session is shared with the repositories so their writes
    commit atomically.
    """

    _session: AsyncSession

    async def __aenter__(self) -> "SqlUoW":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
        except SQLAlchemyError as exc_:
            raise PortError(f"uow finalize failed: {exc_}") from exc_
