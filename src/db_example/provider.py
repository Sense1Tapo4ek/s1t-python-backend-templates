from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide

from shared.app import IClock

from .adapters.db_example_lifespan_manager import DbExampleLifespanManager
from .adapters.driven.db.connection import open_connection
from .adapters.driven.db.sqlite_pool import SqlitePool
from .app import ItemManagement, ItemQueries
from .config import DbExampleConfig
from .ports.driven.repos import SqliteItemRepo
from .ports.driving import PerRequestItemFacade, PooledItemFacade


class DbExampleInfraProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> DbExampleConfig:
        return DbExampleConfig()

    @provide
    def pool(self, config: DbExampleConfig) -> SqlitePool:
        assert config.db_path is not None
        return SqlitePool(config.db_path, config.pool_size)

    @provide
    def lifespan(self, config: DbExampleConfig, pool: SqlitePool) -> DbExampleLifespanManager:
        return DbExampleLifespanManager(config=config, pool=pool)


class PooledDbExampleProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(self, pool: SqlitePool, clock: IClock) -> AsyncIterator[PooledItemFacade]:
        async with pool.acquire() as conn:
            repo = SqliteItemRepo(_conn=conn)
            yield PooledItemFacade(
                _mgmt=ItemManagement(_repo=repo, _clock=clock),
                _queries=ItemQueries(_repo=repo),
            )


class PerRequestDbExampleProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(self, config: DbExampleConfig, clock: IClock) -> AsyncIterator[PerRequestItemFacade]:
        assert config.db_path is not None
        conn = await open_connection(config.db_path)
        try:
            repo = SqliteItemRepo(_conn=conn)
            yield PerRequestItemFacade(
                _mgmt=ItemManagement(_repo=repo, _clock=clock),
                _queries=ItemQueries(_repo=repo),
            )
        finally:
            await conn.close()
