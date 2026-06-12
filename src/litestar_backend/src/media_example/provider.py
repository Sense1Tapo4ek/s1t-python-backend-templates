from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import redis.asyncio as aioredis
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.adapters.driven.postgres import SqlUoW, build_engine, build_sessionmaker
from shared.app import IClock
from shared.config import PostgresConfig

from .adapters.driven.outbox_relay import OutboxRelay
from .adapters.lifespan_manager import MediaLifespanManager
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


class _NoopFeed:
    # Task 6 replaces this with ChannelsFeedPublisher via DI
    async def publish(self, video_id: UUID, status: str) -> None:  # pragma: no cover
        return None


@dataclass(frozen=True, slots=True)
class MediaDb:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]


class MediaInfraProvider(Provider):
    scope = Scope.APP

    config = provide(MediaConfig)

    @provide
    async def db(self, pg: PostgresConfig, config: MediaConfig) -> AsyncIterator[MediaDb]:
        engine = build_engine(pg.alchemy_url, config.schema_name, pool_size=config.pool_size)
        try:
            yield MediaDb(engine=engine, sessionmaker=build_sessionmaker(engine))
        finally:
            await engine.dispose()

    @provide
    def relay(self, db: MediaDb, valkey: aioredis.Redis, config: MediaConfig) -> OutboxRelay:
        return OutboxRelay(
            _sessionmaker=db.sessionmaker,
            _valkey=valkey,
            _batch=config.relay_batch,
            _idle_sleep=config.relay_idle_sleep,
        )

    @provide
    def lifespan(self, pg: PostgresConfig, relay: OutboxRelay) -> MediaLifespanManager:
        return MediaLifespanManager(yoyo_url=pg.yoyo_url, relay=relay)


class MediaWebProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(self, db: MediaDb, clock: IClock) -> AsyncIterator[MediaFacade]:
        async with db.sessionmaker() as session:
            repo = SqlVideoRepo(_session=session)
            outbox = SqlOutboxRepo(_session=session)
            uow = SqlUoW(_session=session)
            _feed = _NoopFeed()
            yield MediaFacade(
                _upload=UploadVideoUC(_repo=repo, _uow=uow, _outbox=outbox, _clock=clock),
                _recent=ListVideosQuery(_repo=repo),
                _mark_processing=MarkProcessingUC(_repo=repo, _uow=uow, _feed=_feed),
                _mark_done=MarkDoneUC(_repo=repo, _uow=uow, _feed=_feed),
                _mark_failed=MarkFailedUC(_repo=repo, _uow=uow, _feed=_feed),
            )
