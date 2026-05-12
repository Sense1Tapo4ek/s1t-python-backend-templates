from dishka import Provider, Scope, provide

from .config import MetricsConfig


class AdminMetricsProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> MetricsConfig:
        return MetricsConfig()
