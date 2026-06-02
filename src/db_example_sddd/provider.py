from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide

from shared.app import IClock

from .adapters.db_example_sddd_lifespan_manager import DbExampleSdddLifespanManager
from .adapters.driven.connection import open_connection
from .adapters.driven.sqlite_pool import SqlitePool
from .app import ItemManagement, ItemQueries
from .config import DbExampleSdddConfig
from .ports.driven import SqliteItemRepo
from .ports.driving import PerRequestItemFacade, PooledItemFacade


class DbExampleSdddInfraProvider(Provider):
    scope = Scope.APP

    config = provide(DbExampleSdddConfig)
    lifespan = provide(DbExampleSdddLifespanManager)

    @provide
    def pool(self, config: DbExampleSdddConfig) -> SqlitePool:
        if config.db_path is None:
            raise RuntimeError("DB_EXAMPLE_SDDD_DB_PATH could not be resolved")
        return SqlitePool(config.db_path, config.pool_size)


class PooledDbExampleSdddProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(self, pool: SqlitePool, clock: IClock) -> AsyncIterator[PooledItemFacade]:
        async with pool.acquire() as conn:
            repo = SqliteItemRepo(_conn=conn)
            yield PooledItemFacade(
                _mgmt=ItemManagement(_repo=repo, _clock=clock),
                _queries=ItemQueries(_repo=repo),
            )


class PerRequestDbExampleSdddProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(self, config: DbExampleSdddConfig, clock: IClock) -> AsyncIterator[PerRequestItemFacade]:
        if config.db_path is None:
            raise RuntimeError("DB_EXAMPLE_SDDD_DB_PATH could not be resolved")
        conn = await open_connection(config.db_path)
        try:
            repo = SqliteItemRepo(_conn=conn)
            yield PerRequestItemFacade(
                _mgmt=ItemManagement(_repo=repo, _clock=clock),
                _queries=ItemQueries(_repo=repo),
            )
        finally:
            await conn.close()
