from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from .observability import attach_query_observability


def build_engine(
    alchemy_url: str, schema: str, *, pool_size: int | None = None, observe: bool = True
) -> AsyncEngine:
    # search_path scopes this context to its schema; unqualified table names resolve there.
    extra: dict[str, int] = {} if pool_size is None else {"pool_size": pool_size}
    engine = create_async_engine(
        alchemy_url,
        connect_args={"server_settings": {"search_path": schema}},
        **extra,
    )
    if observe:
        # Core events live on the underlying sync engine.
        attach_query_observability(engine.sync_engine)
    return engine


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def build_probe_engine(alchemy_url: str) -> AsyncEngine:
    # Dedicated readiness engine: NullPool opens a connection on demand and
    # closes it, so a readiness probe never holds an idle connection or
    # competes with a context's request pool. No search_path -- SELECT 1
    # is schema-agnostic.
    return create_async_engine(alchemy_url, poolclass=NullPool)
