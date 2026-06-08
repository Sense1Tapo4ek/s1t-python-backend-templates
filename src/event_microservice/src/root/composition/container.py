import redis.asyncio as aioredis
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from root.config import RootConfig
from shared.adapters.driven.valkey import build_valkey


class RootProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> RootConfig:
        return RootConfig()

    @provide
    def valkey(self, config: RootConfig) -> aioredis.Redis:
        return build_valkey(config.valkey_url)


def build_container() -> AsyncContainer:
    return make_async_container(RootProvider())
