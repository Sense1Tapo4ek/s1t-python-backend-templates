import os
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from shared.generics.config import PROJECT_ROOT, GenericConfig


class AppEnv(StrEnum):
    DEV = "dev"
    PROD = "prod"


class BaseAppConfig(GenericConfig):
    app_name: str = Field(
        default="litestar-base",
        description="Human-readable application name",
        validation_alias="APP_NAME",
    )
    app_env: AppEnv = Field(
        default=AppEnv.DEV,
        description="Application runtime environment",
        validation_alias="APP_ENV",
    )
    volume_path: Path = Field(
        default=PROJECT_ROOT / "storage",
        description="Root directory for all persistent volume data",
        validation_alias="VOLUME_PATH",
    )
    runtime_path: Path | None = Field(
        default=None,
        description="Directory for process runtime files such as pidfiles",
        validation_alias="RUNTIME_PATH",
    )

    @model_validator(mode="after")
    def resolve_paths(self) -> Self:
        if not self.volume_path.is_absolute():
            self.volume_path = self.project_root / self.volume_path

        if self.runtime_path is None:
            self.runtime_path = Path(tempfile.gettempdir()) / self.app_name
        elif not self.runtime_path.is_absolute():
            self.runtime_path = self.project_root / self.runtime_path

        return self

    @property
    def log_dir(self) -> Path:
        return self.volume_path / "logs"


class PostgresConfig(GenericConfig):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    db: str = "litestar_base"

    @property
    def asyncpg_dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def alchemy_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def yoyo_url(self) -> str:
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class ValkeyConfig(GenericConfig):
    model_config = SettingsConfigDict(
        env_prefix="VALKEY_",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 20

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class MetricsConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="METRICS_")

    prom_endpoint_path: str = "/metrics"
    prom_endpoint_public: bool = False
    http_buckets: list[float] = Field(
        default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    multiproc_dir: Path | None = Field(default=None)

    @model_validator(mode="after")
    def resolve_multiproc_dir(self) -> Self:
        # Precedence: PROMETHEUS_MULTIPROC_DIR (prometheus_client's own env --
        # e.g. a compose tmpfs mount) > METRICS_MULTIPROC_DIR > volume_path/prometheus.
        # The library reads PROMETHEUS_MULTIPROC_DIR directly, so it is the single
        # source of truth when present; otherwise we materialize our own path.
        env_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "").strip()
        if env_dir:
            self.multiproc_dir = Path(env_dir)
        elif self.multiproc_dir is None:
            self.multiproc_dir = self.volume_path / "prometheus"
        elif not self.multiproc_dir.is_absolute():
            self.multiproc_dir = self.volume_path / self.multiproc_dir
        return self
