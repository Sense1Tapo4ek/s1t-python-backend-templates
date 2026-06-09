from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from dishka import Provider, Scope, provide

from shared.adapters.driven.clocks import SystemClock
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
        # (aclose) on container teardown. Injected into the media_example
        # outbox relay; the Channels event-bus backend builds its own client
        # in build_app and does not use this provider.
        client = build_valkey_client(cfg.url, max_connections=cfg.max_connections)
        yield client
        await client.aclose()
