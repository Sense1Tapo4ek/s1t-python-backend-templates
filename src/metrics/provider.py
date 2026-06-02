from dishka import Provider, Scope, provide

from .adapters import MetricsLifespanManager
from .adapters.driven import PrometheusSink
from .app import IMetricsSink
from .config import MetricsConfig
from .ports.driving import MetricsFacade


class MetricsProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> MetricsConfig:
        return MetricsConfig()

    @provide
    def lifespan(self, config: MetricsConfig) -> MetricsLifespanManager:
        return MetricsLifespanManager(config=config)

    sink = provide(PrometheusSink, provides=IMetricsSink)
    facade = provide(MetricsFacade)
