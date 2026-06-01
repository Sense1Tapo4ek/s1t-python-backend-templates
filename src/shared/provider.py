from dishka import Provider, Scope, provide

from shared.config import BaseAppConfig


class SharedProvider(Provider):
    scope = Scope.APP

    @provide
    def provide_base_app_config(self) -> BaseAppConfig:
        return BaseAppConfig()
