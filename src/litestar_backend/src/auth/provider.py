from dishka import Provider, Scope, provide

from shared.app import IClock

from .adapters.driven import JwtCodec, JwtKey, build_jwt_key
from .app import (
    AuthenticateUc,
    IDenylist,
    IJwtCodec,
    IJwtIssuer,
    IJwtVerifier,
    ITokenResolver,
)
from .config import AuthConfig
from .ports.driven import (
    CompositeTokenResolver,
    JwtService,
    JwtTokenResolver,
    StaticTokenResolver,
    ValkeyDenylist,
)
from .ports.driving import AuthFacade


class AuthProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AuthConfig:
        return AuthConfig()

    @provide
    def jwt_key(self, config: AuthConfig) -> JwtKey:
        secret = config.jwt_secret
        return build_jwt_key(secret.get_secret_value() if secret else None)

    codec = provide(JwtCodec, provides=IJwtCodec)

    @provide
    def jwt_service(self, codec: IJwtCodec, clock: IClock, config: AuthConfig) -> JwtService:
        return JwtService(
            _codec=codec,
            _clock=clock,
            _issuer=config.jwt_issuer,
            _access_ttl=config.jwt_access_ttl_seconds,
            _refresh_ttl=config.jwt_refresh_ttl_seconds,
        )

    @provide
    def jwt_issuer(self, svc: JwtService) -> IJwtIssuer:
        return svc

    @provide
    def jwt_verifier(self, svc: JwtService) -> IJwtVerifier:
        return svc

    denylist = provide(ValkeyDenylist, provides=IDenylist)

    @provide
    def token_resolver(
        self, verifier: IJwtVerifier, denylist: IDenylist, config: AuthConfig
    ) -> ITokenResolver:
        return CompositeTokenResolver(
            _resolvers=(
                JwtTokenResolver(_verifier=verifier, _denylist=denylist),
                StaticTokenResolver(_config=config),
            )
        )

    authenticate_uc = provide(AuthenticateUc)
    auth_facade = provide(AuthFacade)
