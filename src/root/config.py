from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from auth.config import AuthConfig
from shared.config import AppEnv, BaseAppConfig


class RootConfig(BaseAppConfig):
    app_host: str = Field(
        default="127.0.0.1",
        description="Host interface used by the ASGI server",
        validation_alias="APP_HOST",
    )
    app_port: int = Field(
        default=8000,
        description="Port used by the ASGI server",
        validation_alias="APP_PORT",
    )
    app_workers: int = Field(
        default=1,
        description="Number of ASGI worker processes for production runs",
        ge=1,
        validation_alias="APP_WORKERS",
    )
    shutdown_timeout_s: int = Field(
        default=25,
        description=(
            "Seconds uvicorn waits for inflight requests to drain on SIGTERM "
            "before forcing close. Should be < K8s terminationGracePeriodSeconds "
            "(default 30s) so the orchestrator never SIGKILLs mid-drain."
        ),
        ge=0,
        validation_alias="APP_SHUTDOWN_TIMEOUT_S",
    )
    security_csp: str = Field(
        default=(
            "default-src 'self'; "
            "script-src 'self'; "
            # Inline styles and Google Fonts are needed by the bundled admin
            # dashboard; tighten if you replace the front-end.
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ),
        description=(
            "Content-Security-Policy header attached to every HTTP response. "
            "Override per-deployment to tighten or relax for your front-end."
        ),
        validation_alias="SECURITY_CSP",
    )
    security_hsts_enabled: bool = Field(
        default=False,
        description=(
            "Emit Strict-Transport-Security with a 2-year max-age + "
            "includeSubDomains. Disabled by default because HSTS poisons "
            "browser cache for plaintext dev (http://localhost). Enable "
            "only behind a verified-HTTPS deployment."
        ),
        validation_alias="SECURITY_HSTS_ENABLED",
    )

    @model_validator(mode="after")
    def _validate_prod_invariants(self) -> Self:
        if self.app_env == AppEnv.PROD:
            # Reuse AuthConfig so the same parsing rules apply (env_ignore_empty,
            # whitespace stripping, SecretStr resolution) — checking os.environ
            # directly would diverge from how the runtime actually loads it.
            token = AuthConfig().admin_token
            if token is None or not token.get_secret_value().strip():
                raise ValueError(
                    "AUTH_ADMIN_TOKEN must be set when APP_ENV=PROD"
                )
        return self

    @property
    def should_reload(self) -> bool:
        return self.app_env == AppEnv.DEV

    @property
    def console_log(self) -> Path:
        return self.log_dir / f"{self.app_name}.log"

    @property
    def pidfile(self) -> Path:
        if self.runtime_path is None:
            raise RuntimeError("runtime_path was not resolved by model_validator")
        return self.runtime_path / f"{self.app_name}.pid"
