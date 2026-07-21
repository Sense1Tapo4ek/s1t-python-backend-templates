from collections.abc import AsyncIterator

import redis.asyncio as aioredis
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from saq import Queue

from media_processing import MediaProcessingProvider
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

    # Root owns the broker URL; contexts consume the ready Queue and never
    # reach up into root.config.
    @provide
    def queue(self, config: RootConfig) -> Queue:
        return Queue.from_url(config.valkey_url)


def build_container() -> AsyncContainer:
    return make_async_container(RootProvider(), MediaProcessingProvider())
