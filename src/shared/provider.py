from dishka import Provider, Scope, provide

from shared.adapters.driven.clocks import SystemClock
from shared.app import IClock
from shared.config import BaseAppConfig, PostgresConfig


class SharedProvider(Provider):
    scope = Scope.APP

    clock = provide(SystemClock, provides=IClock)

    @provide
    def provide_base_app_config(self) -> BaseAppConfig:
        return BaseAppConfig()

    @provide
    def provide_postgres_config(self) -> PostgresConfig:
        return PostgresConfig()
