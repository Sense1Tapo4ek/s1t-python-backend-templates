from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig

ADMIN_COOKIE_NAME = "admin_token"

# Tokens are 64 hex chars (256 bits) by convention. 4 KiB is ~64x that — way
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
