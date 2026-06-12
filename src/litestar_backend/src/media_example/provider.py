from collections.abc import AsyncIterator
from dataclasses import dataclass

import redis.asyncio as aioredis
from dishka import Provider, Scope, from_context, provide
from litestar.channels import ChannelsPlugin
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.adapters.driven.postgres import SqlUoW, build_engine, build_sessionmaker
from shared.app import IClock
from shared.config import PostgresConfig

from .adapters.driven.outbox_relay import OutboxRelay
from .adapters.driving.status_consumer import VideoStatusConsumer
from .adapters.lifespan_manager import MediaLifespanManager
from .app import (
    IFeedPublisher,
    ListVideosQuery,
    MarkDoneUC,
    MarkFailedUC,
    MarkProcessingUC,
    UploadVideoUC,
)
from .config import MediaConfig
from .ports.driven.channels_feed_publisher import ChannelsFeedPublisher
from .ports.driven.sql_outbox_repo import SqlOutboxRepo
from .ports.driven.sql_video_repo import SqlVideoRepo
from .ports.driving.media_facade import MediaFacade


@dataclass(frozen=True, slots=True)
class MediaDb:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]


def build_facade(session: AsyncSession, clock: IClock, feed: IFeedPublisher) -> MediaFacade:
    repo = SqlVideoRepo(_session=session)
    outbox = SqlOutboxRepo(_session=session)
    uow = SqlUoW(_session=session)
    return MediaFacade(
        _upload=UploadVideoUC(_repo=repo, _uow=uow, _outbox=outbox, _clock=clock),
        _recent=ListVideosQuery(_repo=repo),
        _mark_processing=MarkProcessingUC(_repo=repo, _uow=uow, _feed=feed),
        _mark_done=MarkDoneUC(_repo=repo, _uow=uow, _feed=feed),
        _mark_failed=MarkFailedUC(_repo=repo, _uow=uow, _feed=feed),
    )


class MediaInfraProvider(Provider):
    scope = Scope.APP

    config = provide(MediaConfig)

    channels = from_context(provides=ChannelsPlugin, scope=Scope.APP)

    @provide
    async def db(self, pg: PostgresConfig, config: MediaConfig) -> AsyncIterator[MediaDb]:
        engine = build_engine(pg.alchemy_url, config.schema_name, pool_size=config.pool_size)
        try:
            yield MediaDb(engine=engine, sessionmaker=build_sessionmaker(engine))
        finally:
            await engine.dispose()

    @provide
    def feed(self, channels: ChannelsPlugin) -> IFeedPublisher:
        return ChannelsFeedPublisher(_channels=channels)

    @provide
    def relay(self, db: MediaDb, valkey: aioredis.Redis, config: MediaConfig) -> OutboxRelay:
        return OutboxRelay(
            _sessionmaker=db.sessionmaker,
            _valkey=valkey,
            _batch=config.relay_batch,
            _idle_sleep=config.relay_idle_sleep,
        )

    @provide
    def status_consumer(
        self,
        db: MediaDb,
        valkey: aioredis.Redis,
        clock: IClock,
        feed: IFeedPublisher,
        config: MediaConfig,
    ) -> VideoStatusConsumer:
        return VideoStatusConsumer(
            _valkey=valkey,
            _sessionmaker=db.sessionmaker,
            _facade_factory=lambda session: build_facade(session, clock, feed),
            _batch=config.status_batch,
            _block_ms=config.status_block_ms,
            _claim_idle_ms=config.status_claim_idle_ms,
        )

    @provide
    def lifespan(
        self, pg: PostgresConfig, relay: OutboxRelay, consumer: VideoStatusConsumer
    ) -> MediaLifespanManager:
        return MediaLifespanManager(yoyo_url=pg.yoyo_url, relay=relay, consumer=consumer)


class MediaWebProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def facade(
        self, db: MediaDb, clock: IClock, feed: IFeedPublisher
    ) -> AsyncIterator[MediaFacade]:
        async with db.sessionmaker() as session:
            yield build_facade(session, clock, feed)
