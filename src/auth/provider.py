from dishka import Provider, Scope, provide

from .app import AuthenticateUc
from .app.interfaces import ITokenResolver
from .config import AuthConfig
from .ports.driven.gateways import StaticTokenResolver
from .ports.driving.facades import AuthFacade


class AuthPortBindings(Provider):
    scope = Scope.APP

    token_resolver = provide(StaticTokenResolver, provides=ITokenResolver)


class AuthProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AuthConfig:
        return AuthConfig()

    authenticate_uc = provide(AuthenticateUc)
    auth_facade = provide(AuthFacade)
