import os
import socket
from datetime import UTC, datetime

from dishka import Provider, Scope, collect, provide
from redis.asyncio import Redis

from shared.config import BaseAppConfig

from .adapters.driven.samplers import EventLoopLagSampler, ProcessRssSampler
from .adapters.driven.workers import MetricsPublisherWorker
from .adapters.lifespan import MetricsLifespanManager
from .app.interfaces import (
    ILoopLagSampler,
    IMetricsModulePlugin,
    IMetricsPublisher,
    IModulePluginRegistry,
    IRssSampler,
)
from .app.use_cases import PublishWorkerSnapshotUc
from .config import MetricsConfig
from .domain import WorkerIdVo
from .ports.driven.collectors import ValkeyAggregatedCollector
from .ports.driven.dispatchers import RedisMetricsPublisher
from .ports.driven.plugins import HttpMetricsPlugin, WorkersMetricsPlugin
from .ports.driven.registry import InMemoryModulePluginRegistry


def _build_redis_client(base: BaseAppConfig) -> Redis:
    return Redis.from_url(base.valkey_url, decode_responses=False)


class AdminMetricsProvider(Provider):
    scope = Scope.APP

    _collect_plugins = collect(IMetricsModulePlugin)

    @provide
    def config(self) -> MetricsConfig:
        return MetricsConfig()

    @provide
    def redis(self, base: BaseAppConfig) -> Redis:
        return _build_redis_client(base)

    @provide(provides=IMetricsModulePlugin)
    def workers_plugin(
        self,
        redis: Redis,
        config: MetricsConfig,
    ) -> WorkersMetricsPlugin:
        return WorkersMetricsPlugin(
            _redis=redis,
            _key_prefix=config.key_prefix,
        )

    @provide(provides=IMetricsModulePlugin)
    def http_plugin(self, config: MetricsConfig) -> HttpMetricsPlugin:
        return HttpMetricsPlugin(
            _prefix=f"{config.key_prefix.rstrip(':')}_http",
        )

    @provide(provides=IModulePluginRegistry)
    def plugin_registry(
        self,
        plugins: list[IMetricsModulePlugin],
    ) -> InMemoryModulePluginRegistry:
        return InMemoryModulePluginRegistry(_plugins=tuple(plugins))

    @provide
    def worker_id(self) -> WorkerIdVo:
        return WorkerIdVo(host=socket.gethostname(), pid=os.getpid())

    @provide
    def started_at(self) -> datetime:
        return datetime.now(UTC)

    @provide(provides=ILoopLagSampler)
    def loop_lag_sampler(self, config: MetricsConfig) -> EventLoopLagSampler:
        return EventLoopLagSampler(
            _interval_s=config.publish_interval_s / 5,
            _window=60,
        )

    @provide(provides=IRssSampler)
    def rss_sampler(self) -> ProcessRssSampler:
        return ProcessRssSampler()

    @provide(provides=IMetricsPublisher)
    def metrics_publisher(
        self,
        redis: Redis,
        config: MetricsConfig,
    ) -> RedisMetricsPublisher:
        return RedisMetricsPublisher(
            _redis=redis,
            _key_prefix=config.key_prefix,
            _key_ttl_s=config.key_ttl_s,
        )

    @provide
    def aggregated_collector(
        self,
        redis: Redis,
        config: MetricsConfig,
    ) -> ValkeyAggregatedCollector:
        return ValkeyAggregatedCollector(
            _redis=redis,  # type: ignore[arg-type]  # redis-py stub vs local Protocol
            _key_prefix=config.key_prefix,
        )

    @provide
    def publish_uc(
        self,
        publisher: IMetricsPublisher,
        loop_lag: ILoopLagSampler,
        rss: IRssSampler,
        worker_id: WorkerIdVo,
        started_at: datetime,
        base: BaseAppConfig,
    ) -> PublishWorkerSnapshotUc:
        role = "sink" if base.app_name.endswith("-sink") else "api"
        return PublishWorkerSnapshotUc(
            _publisher=publisher,
            _loop_lag_sampler=loop_lag,
            _rss_sampler=rss,
            _queue_depth_provider=None,
            _worker_id=worker_id,
            _role=role,
            _started_at=started_at,
        )

    @provide
    def publisher_worker(
        self,
        uc: PublishWorkerSnapshotUc,
        config: MetricsConfig,
    ) -> MetricsPublisherWorker:
        return MetricsPublisherWorker(
            _use_case=uc.__call__,
            _interval_s=config.publish_interval_s,
        )

    @provide
    def lifespan(
        self,
        loop_lag: ILoopLagSampler,
        worker: MetricsPublisherWorker,
        collector: ValkeyAggregatedCollector,
    ) -> MetricsLifespanManager:
        return MetricsLifespanManager(
            _loop_lag_sampler=loop_lag,
            _publisher_worker=worker,
            _aggregated_collector=collector,
        )
