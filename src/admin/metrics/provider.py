from dishka import Provider, Scope, collect, provide

from .app.interfaces import IMetricsModulePlugin, IModulePluginRegistry
from .config import MetricsConfig
from .ports.driven.registry import InMemoryModulePluginRegistry


class AdminMetricsProvider(Provider):
    scope = Scope.APP

    # Declares the list[IMetricsModulePlugin] aggregator so Dishka collects
    # all IMetricsModulePlugin instances provided across all providers into
    # a single list.
    _collect_plugins = collect(IMetricsModulePlugin)

    @provide
    def config(self) -> MetricsConfig:
        return MetricsConfig()

    @provide(provides=IModulePluginRegistry)
    def plugin_registry(
        self,
        plugins: list[IMetricsModulePlugin],
    ) -> InMemoryModulePluginRegistry:
        return InMemoryModulePluginRegistry(_plugins=tuple(plugins))
