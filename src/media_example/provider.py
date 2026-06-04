from collections.abc import AsyncIterator
from dataclasses import dataclass

import asyncpg
import redis.asyncio as aioredis
from dishka import Provider, Scope, provide

from shared.adapters.driven.postgres import SqlUoW, build_pool
from shared.app import IClock
from shared.config import PostgresConfig

from .adapters.driven.outbox_relay import OutboxRelay
from .adapters.media_example_lifespan_manager import MediaLifespanManager
from .app import (
    ListVideosQuery,
    MarkDoneUC,
    MarkFailedUC,
    MarkProcessingUC,
    UploadVideoUC,
)
from .config import MediaConfig
from .ports.driven.sql_outbox_repo import SqlOutboxRepo
from .ports.driven.sql_video_repo import SqlVideoRepo
from .ports.driving.media_facade import MediaFacade


@dataclass(frozen=True, slots=True)
class MediaPool:
    raw: asyncpg.Pool


class MediaInfraProvider(Provider):
    scope = Scope.APP

    config = provide(MediaConfig)

    @provide
    async def pool(self, pg: PostgresConfig, config: MediaConfig) -> MediaPool:
        return MediaPool(raw=await build_pool(pg.asyncpg_dsn, schema=config.schema_name, size=config.pool_size))

    @provide
    def relay(self, pool: MediaPool, valkey: aioredis.Redis, config: MediaConfig) -> OutboxRelay:
        return OutboxRelay(_pool=pool.raw, _valkey=valkey, _batch=config.relay_batch, _idle_sleep=config.relay_idle_sleep)

    @provide
    def lifespan(self, pool: MediaPool, pg: PostgresConfig, relay: OutboxRelay) -> MediaLifespanManager:
        return MediaLifespanManager(pool=pool.raw, yoyo_url=pg.yoyo_url, relay=relay)


class MediaWebProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(self, pool: MediaPool, clock: IClock) -> AsyncIterator[MediaFacade]:
        async with pool.raw.acquire() as conn:
            repo = SqlVideoRepo(_conn=conn)
            outbox = SqlOutboxRepo(_conn=conn)
            uow = SqlUoW(_conn=conn)
            yield MediaFacade(
                _upload=UploadVideoUC(_repo=repo, _uow=uow, _outbox=outbox, _clock=clock),
                _recent=ListVideosQuery(_repo=repo),
                _mark_processing=MarkProcessingUC(_repo=repo, _uow=uow),
                _mark_done=MarkDoneUC(_repo=repo, _uow=uow),
                _mark_failed=MarkFailedUC(_repo=repo, _uow=uow),
            )
