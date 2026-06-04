from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from dishka import Provider, Scope, provide

from shared.adapters.driven.clocks import SystemClock
from shared.adapters.driven.redis import build_redis_client
from shared.app import IClock
from shared.config import BaseAppConfig, PostgresConfig, RedisConfig


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
    def provide_redis_config(self) -> RedisConfig:
        return RedisConfig()

    @provide
    async def provide_redis_client(self, cfg: RedisConfig) -> AsyncIterator[aioredis.Redis]:
        # APP-scope, lazy: constructed only when first injected; Dishka closes
        # the generator (aclose) on container teardown. No consumer in Phase 1 --
        # the Channels backend builds its own client in build_app -- but the
        # provider lands here as the canonical home for Phase 2/3 (SAQ, dedup).
        client = build_redis_client(cfg.url, max_connections=cfg.max_connections)
        yield client
        await client.aclose()
