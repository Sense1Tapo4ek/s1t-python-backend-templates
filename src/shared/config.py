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
