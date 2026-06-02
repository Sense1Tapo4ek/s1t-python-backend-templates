from dishka import Provider, Scope, provide

from .adapters import MetricsLifespanManager
from .config import MetricsConfig


class MetricsProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> MetricsConfig:
        return MetricsConfig()

    @provide
    def lifespan(self, config: MetricsConfig) -> MetricsLifespanManager:
        return MetricsLifespanManager(config=config)
