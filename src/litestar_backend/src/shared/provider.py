from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from dishka import Provider, Scope, provide

from shared.adapters.driven.clocks import SystemClock
from shared.adapters.driven.postgres import build_probe_engine
from shared.adapters.driven.readiness import ReadinessProbe
from shared.adapters.driven.valkey import build_valkey_client
from shared.app import IClock
from shared.config import BaseAppConfig, PostgresConfig, ValkeyConfig


class SharedProvider(Provider):
    scope = Scope.APP

    clock = provide(SystemClock, provides=IClock)

    @provide
    def provide_base_app_config(self) -> BaseAppConfig:
        return BaseAppConfig()

    @provide
    def provide_postgres_config(self) -> PostgresConfig:
        return PostgresConfig()

    @provide
    def provide_valkey_config(self) -> ValkeyConfig:
        return ValkeyConfig()

    @provide
    async def provide_valkey_client(self, cfg: ValkeyConfig) -> AsyncIterator[aioredis.Redis]:
        # APP-scope, lazy: constructed on first injection, closed by Dishka
        # (aclose) on container teardown. The Channels event-bus backend
        # builds its own client and does not use this provider.
        client = build_valkey_client(cfg.url, max_connections=cfg.max_connections)
        yield client
        await client.aclose()

    @provide
    async def provide_readiness_probe(
        self, pg: PostgresConfig, valkey: aioredis.Redis
    ) -> AsyncIterator[ReadinessProbe]:
        # Own NullPool engine so readiness never borrows a context's request
        # pool; disposed on container teardown.
        engine = build_probe_engine(pg.alchemy_url)
        try:
            yield ReadinessProbe(_engine=engine, _valkey=valkey)
        finally:
            await engine.dispose()
