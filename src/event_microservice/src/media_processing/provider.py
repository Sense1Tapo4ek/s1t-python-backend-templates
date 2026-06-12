import redis.asyncio as aioredis
from dishka import Provider, Scope, provide
from saq import Queue

from root.config import RootConfig

from .app import CompleteJobUC, IEventPublisher, IJobQueue, IJoinStore, OnVideoUploadedUC
from .config import MediaProcessingConfig
from .domain import JobKind
from .ports.driven import SaqJobQueue, ValkeyEventPublisher, ValkeyJoinStore
from .ports.driving import MediaProcessingFacade


class MediaProcessingProvider(Provider):
    scope = Scope.APP

    on_uploaded = provide(OnVideoUploadedUC)
    facade = provide(MediaProcessingFacade)

    @provide
    def config(self) -> MediaProcessingConfig:
        return MediaProcessingConfig()

    @provide
    def queue(self, root: RootConfig) -> Queue:
        return Queue.from_url(root.valkey_url)

    @provide
    def job_queue(self, queue: Queue, config: MediaProcessingConfig) -> IJobQueue:
        return SaqJobQueue(_queue=queue, _retries=config.job_retries, _timeout=config.job_timeout_seconds)

    @provide
    def join_store(self, valkey: aioredis.Redis, config: MediaProcessingConfig) -> IJoinStore:
        return ValkeyJoinStore(_valkey=valkey, _ttl_seconds=config.join_ttl_seconds)

    @provide
    def publisher(self, valkey: aioredis.Redis) -> IEventPublisher:
        return ValkeyEventPublisher(_valkey=valkey)

    @provide
    def complete_job(self, join_store: IJoinStore, publisher: IEventPublisher) -> CompleteJobUC:
        return CompleteJobUC(_store=join_store, _fan_out=len(JobKind), _publisher=publisher)
