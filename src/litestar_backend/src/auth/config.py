from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig

ADMIN_COOKIE_NAME = "admin_token"

# Tokens are 64 hex chars (256 bits) by convention. 4 KiB is ~64x that -- way
# more headroom than any legitimate token needs, while keeping `compare_digest`
# input from being weaponised into a memory/CPU sink.
MAX_TOKEN_LEN = 4096


class AuthConfig(BaseAppConfig):
    """`admin_token` empty in dev disables auth (middleware logs a warning).
    Production must set it (validated by RootConfig).
    """

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_ignore_empty=True,
    )

    admin_token: SecretStr | None = Field(
        default=None,
        description="Bearer token granting Role.ADMIN. Empty disables auth in dev.",
    )
    jwt_secret: SecretStr | None = Field(
        default=None,
        description="HS256 signing secret for JWT. Empty disables JWT issuance/verification.",
    )
    jwt_issuer: str = Field(
        default="litestar-base",
        description="Value of the JWT 'iss' claim; verified on decode.",
    )
    jwt_access_ttl_seconds: int = Field(
        default=900,
        ge=1,
        description="Access-token lifetime in seconds (default 15 min).",
    )
    jwt_refresh_ttl_seconds: int = Field(
        default=1_209_600,
        ge=1,
        description="Refresh-token lifetime in seconds (default 14 days).",
    )
    schema_name: str = Field(default="auth", description="Postgres schema for the auth context.")
    pool_size: int = Field(default=5, ge=1, description="SQLAlchemy pool size for the auth engine.")
