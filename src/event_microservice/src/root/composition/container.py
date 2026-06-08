from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from media_processing.provider import MediaProcessingProvider
from root.config import RootConfig
from shared.adapters.driven.valkey import build_valkey


class RootProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> RootConfig:
        return RootConfig()

    @provide
    async def valkey(self, config: RootConfig) -> AsyncIterator[aioredis.Redis]:
        client = build_valkey(config.valkey_url)
        try:
            yield client
        finally:
            await client.aclose()


def build_container() -> AsyncContainer:
    return make_async_container(RootProvider(), MediaProcessingProvider())
