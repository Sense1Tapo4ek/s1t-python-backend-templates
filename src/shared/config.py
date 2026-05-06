import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from shared.generics.config import PROJECT_ROOT, GenericConfig


class AppEnv(StrEnum):
    DEV = "dev"
    PROD = "prod"


class BaseAppConfig(GenericConfig):
    """Base configuration shared across every entrypoint of the application."""

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
