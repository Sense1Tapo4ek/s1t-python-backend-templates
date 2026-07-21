import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class RootConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    valkey_url: str = "redis://localhost:6379/0"
    app_env: str = "dev"

    def validate_prod_invariants(self) -> None:
        """Fail startup on prod-unsafe config.

        The SAQ web panel (job abort/retry) is served with HTTP Basic auth
        read from AUTH_PASSWORD (saq's own env contract); an empty value in
        prod would expose job control unauthenticated.

        Raises:
            RuntimeError: APP_ENV=prod and AUTH_PASSWORD is empty.
        """
        if self.app_env != "prod":
            return
        if not os.environ.get("AUTH_PASSWORD"):
            raise RuntimeError(
                "APP_ENV=prod requires a non-empty AUTH_PASSWORD "
                "(SAQ web panel HTTP Basic auth; set SAQ_WEB_PASSWORD in .env)"
            )
