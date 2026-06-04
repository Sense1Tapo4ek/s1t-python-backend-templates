from collections.abc import AsyncIterator
from typing import cast

import asyncpg
from dishka import Provider, Scope, provide
from litestar import Litestar

from shared.app import IClock
from shared.config import PostgresConfig

from .adapters.driven.pg_pool import build_pool
from .adapters.orders_lifespan_manager import OrdersLifespanManager
from .app import IEventBus, ListRecentOrdersQuery, PlaceOrderUC
from .config import OrdersConfig
from .ports.driven import LitestarEventBus, SqlOrderRepo, SqlUoW
from .ports.driven.litestar_event_bus import _Emitter
from .ports.driving import OrdersFacade


class OrdersInfraProvider(Provider):
    scope = Scope.APP

    config = provide(OrdersConfig)

    @provide
    def event_bus(self, app: Litestar) -> IEventBus:
        # Litestar.emit(*args, **kwargs) is a superset of _Emitter; cast is safe.
        return LitestarEventBus(_emitter=cast(_Emitter, app))

    @provide
    async def pool(self, pg: PostgresConfig, config: OrdersConfig) -> asyncpg.Pool:
        return await build_pool(pg.asyncpg_dsn, schema=config.schema_name, size=config.pool_size)

    @provide
    def lifespan(self, pool: asyncpg.Pool, pg: PostgresConfig) -> OrdersLifespanManager:
        return OrdersLifespanManager(pool=pool, yoyo_url=pg.yoyo_url)


class OrdersWebProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(
        self, pool: asyncpg.Pool, clock: IClock, event_bus: IEventBus
    ) -> AsyncIterator[OrdersFacade]:
        async with pool.acquire() as conn:
            repo = SqlOrderRepo(_conn=conn)
            uow = SqlUoW(_conn=conn)
            yield OrdersFacade(
                _place_uc=PlaceOrderUC(_repo=repo, _uow=uow, _event_bus=event_bus, _clock=clock),
                _recent=ListRecentOrdersQuery(_repo=repo),
            )
