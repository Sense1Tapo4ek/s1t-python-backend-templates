from dishka import Provider, Scope, provide

from .app import AuthenticateUc
from .app.interfaces import ITokenResolver
from .config import AuthConfig
from .ports.driven.gateways import StaticTokenResolver
from .ports.driving import AuthFacade


class AuthProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AuthConfig:
        return AuthConfig()

    token_resolver = provide(StaticTokenResolver, provides=ITokenResolver)
    authenticate_uc = provide(AuthenticateUc)
    auth_facade = provide(AuthFacade)
