from collections.abc import AsyncIterator
from dataclasses import dataclass

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.driven.postgres import build_engine, build_sessionmaker
from shared.app import IClock
from shared.config import PostgresConfig

from .adapters.auth_lifespan_manager import AuthLifespanManager
from .adapters.driven import JwtCodec, JwtKey, build_jwt_key
from .app import (
    AuthenticateUc,
    GenerateApiKeyUC,
    IApiKeyRepo,
    IDenylist,
    IJwtCodec,
    IJwtService,
    IssueTokensUC,
    ITokenResolver,
    ListApiKeysUC,
    RefreshTokensUC,
    RevokeApiKeyUC,
    RevokeTokenUC,
)
from .config import AuthConfig
from .ports.driven import (
    ApiKeyResolver,
    CompositeTokenResolver,
    JwtService,
    JwtTokenResolver,
    SqlApiKeyRepo,
    StaticTokenResolver,
    ValkeyDenylist,
)
from .ports.driving import AuthFacade


@dataclass(frozen=True, slots=True)
class AuthDb:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker


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
    def jwt_service_iface(self, svc: JwtService) -> IJwtService:
        return svc

    denylist = provide(ValkeyDenylist, provides=IDenylist)

    @provide
    async def db(self, pg: PostgresConfig, config: AuthConfig) -> AsyncIterator[AuthDb]:
        engine = build_engine(pg.alchemy_url, config.schema_name, pool_size=config.pool_size)
        try:
            yield AuthDb(engine=engine, sessionmaker=build_sessionmaker(engine))
        finally:
            await engine.dispose()

    @provide
    def api_key_repo(self, db: AuthDb) -> IApiKeyRepo:
        return SqlApiKeyRepo(_sessionmaker=db.sessionmaker)

    @provide
    def lifespan(self, pg: PostgresConfig) -> AuthLifespanManager:
        return AuthLifespanManager(yoyo_url=pg.yoyo_url)

    @provide
    def token_resolver(
        self,
        jwt: IJwtService,
        denylist: IDenylist,
        repo: IApiKeyRepo,
        config: AuthConfig,
    ) -> ITokenResolver:
        return CompositeTokenResolver(
            _resolvers=(
                JwtTokenResolver(_jwt=jwt, _denylist=denylist),
                ApiKeyResolver(_repo=repo),
                StaticTokenResolver(_config=config),
            )
        )

    authenticate_uc = provide(AuthenticateUc)
    issue_uc = provide(IssueTokensUC)
    refresh_uc = provide(RefreshTokensUC)
    revoke_uc = provide(RevokeTokenUC)
    generate_api_key_uc = provide(GenerateApiKeyUC)
    list_api_keys_uc = provide(ListApiKeysUC)
    revoke_api_key_uc = provide(RevokeApiKeyUC)
    auth_facade = provide(AuthFacade)
