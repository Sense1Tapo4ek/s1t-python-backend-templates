from collections.abc import AsyncIterator
from dataclasses import dataclass

import redis.asyncio as aioredis
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from shared.adapters.driven.outbox_relay import OutboxRelay
from shared.adapters.driven.postgres import build_engine, build_sessionmaker
from shared.app import IClock
from shared.config import PostgresConfig

from .adapters.auth_lifespan_manager import AuthLifespanManager
from .adapters.driven import JwtCodec, JwtKey, build_jwt_key
from .app import (
    AuthenticateUc,
    DeactivateUserUC,
    GenerateApiKeyUC,
    IApiKeyRepo,
    IDenylist,
    IJwtCodec,
    IJwtService,
    IPasswordHasher,
    IssueTokensUC,
    ITokenResolver,
    IUserRepo,
    ListApiKeysUC,
    ListUsersUC,
    LoginUserUC,
    RefreshTokensUC,
    RegisterUserUC,
    RevokeApiKeyUC,
    RevokeTokenUC,
)
from .config import AuthConfig
from .ports.driven import (
    ApiKeyResolver,
    Argon2Hasher,
    CompositeTokenResolver,
    JwtService,
    JwtTokenResolver,
    SqlApiKeyRepo,
    SqlUserRepo,
    StaticTokenResolver,
    ValkeyDenylist,
)
from .ports.driven.integration_events import USER_REGISTERED_STREAM
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
    def user_repo(self, db: AuthDb, clock: IClock) -> IUserRepo:
        return SqlUserRepo(_sessionmaker=db.sessionmaker, _clock=clock)

    hasher = provide(Argon2Hasher, provides=IPasswordHasher)

    @provide
    def lifespan(
        self, pg: PostgresConfig, db: AuthDb, valkey: aioredis.Redis
    ) -> AuthLifespanManager:
        # The relay is built inline, NOT provided as OutboxRelay: media's
        # provider already provides that type and Dishka resolves by type.
        relay = OutboxRelay(
            _sessionmaker=db.sessionmaker,
            _valkey=valkey,
            _stream=USER_REGISTERED_STREAM,
        )
        return AuthLifespanManager(yoyo_url=pg.yoyo_url, relay=relay)

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
    register_uc = provide(RegisterUserUC)
    login_uc = provide(LoginUserUC)
    list_users_uc = provide(ListUsersUC)
    deactivate_user_uc = provide(DeactivateUserUC)
    generate_api_key_uc = provide(GenerateApiKeyUC)
    list_api_keys_uc = provide(ListApiKeysUC)
    revoke_api_key_uc = provide(RevokeApiKeyUC)
    auth_facade = provide(AuthFacade)
