import redis.asyncio as aioredis
from dishka import Provider, Scope, provide
from saq import Queue

from root.config import RootConfig

from .app import CompleteJobUC, IJobQueue, IJoinStore, OnVideoUploadedUC
from .config import MediaProcessingConfig
from .ports.driven import SaqJobQueue, ValkeyJoinStore
from .ports.driving import MediaProcessingFacade


class MediaProcessingProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> MediaProcessingConfig:
        return MediaProcessingConfig()

    @provide
    def queue(self, root: RootConfig) -> Queue:
        return Queue.from_url(root.valkey_url)

    @provide
    def job_queue(self, queue: Queue) -> IJobQueue:
        return SaqJobQueue(_queue=queue)

    @provide
    def join_store(self, valkey: aioredis.Redis, config: MediaProcessingConfig) -> IJoinStore:
        return ValkeyJoinStore(_valkey=valkey, _ttl_seconds=config.join_ttl_seconds)

    @provide
    def on_uploaded(self, job_queue: IJobQueue) -> OnVideoUploadedUC:
        return OnVideoUploadedUC(_queue=job_queue)

    @provide
    def complete_job(self, join_store: IJoinStore, config: MediaProcessingConfig) -> CompleteJobUC:
        return CompleteJobUC(_store=join_store, _fan_out=config.fan_out)

    @provide
    def facade(self, on_uploaded: OnVideoUploadedUC, complete_job: CompleteJobUC) -> MediaProcessingFacade:
        return MediaProcessingFacade(_on_uploaded=on_uploaded, _complete_job=complete_job)
