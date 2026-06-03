from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(alchemy_url: str, schema: str) -> AsyncEngine:
    # search_path scopes this context to its schema; unqualified table names resolve there.
    return create_async_engine(
        alchemy_url,
        connect_args={"server_settings": {"search_path": schema}},
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
