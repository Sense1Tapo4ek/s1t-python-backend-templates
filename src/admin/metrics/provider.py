from dishka import Provider, Scope, collect, provide
from redis.asyncio import Redis

from shared.config import BaseAppConfig

from .app.interfaces import IMetricsModulePlugin, IModulePluginRegistry
from .config import MetricsConfig
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
