from collections.abc import AsyncIterator

import asyncpg
from dishka import Provider, Scope, provide

from shared.app import IClock
from shared.config import PostgresConfig

from .adapters.db_example_sddd_lifespan_manager import DbExampleSdddLifespanManager
from .adapters.driven.pg_pool import build_pool, open_connection
from .app import IMetrics, ItemManagement, ItemQueries
from .config import DbExampleSdddConfig
from .ports.driven import PgItemRepo
from .ports.driven.acl import MetricsAcl
from .ports.driving import PerRequestItemFacade, PooledItemFacade


class DbExampleSdddInfraProvider(Provider):
    scope = Scope.APP

    config = provide(DbExampleSdddConfig)
    metrics = provide(MetricsAcl, provides=IMetrics)

    @provide
    async def pool(self, pg: PostgresConfig, config: DbExampleSdddConfig) -> asyncpg.Pool:
        return await build_pool(pg.asyncpg_dsn, schema=config.schema_name, size=config.pool_size)

    @provide
    def lifespan(self, pool: asyncpg.Pool, pg: PostgresConfig) -> DbExampleSdddLifespanManager:
        return DbExampleSdddLifespanManager(pool=pool, yoyo_url=pg.yoyo_url)


class PooledDbExampleSdddProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(
        self, pool: asyncpg.Pool, clock: IClock, metrics: IMetrics
    ) -> AsyncIterator[PooledItemFacade]:
        async with pool.acquire() as conn:
            repo = PgItemRepo(_conn=conn)
            yield PooledItemFacade(
                _mgmt=ItemManagement(_repo=repo, _clock=clock, _metrics=metrics),
                _queries=ItemQueries(_repo=repo),
            )


class PerRequestDbExampleSdddProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(
        self, pg: PostgresConfig, config: DbExampleSdddConfig, clock: IClock, metrics: IMetrics
    ) -> AsyncIterator[PerRequestItemFacade]:
        conn = await open_connection(pg.asyncpg_dsn, schema=config.schema_name)
        try:
            repo = PgItemRepo(_conn=conn)
            yield PerRequestItemFacade(
                _mgmt=ItemManagement(_repo=repo, _clock=clock, _metrics=metrics),
                _queries=ItemQueries(_repo=repo),
            )
        finally:
            await conn.close()
