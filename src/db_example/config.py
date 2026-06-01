from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class DbExampleConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="DB_EXAMPLE_")

    db_path: Path | None = Field(default=None)
    pool_size: int = Field(default=4, ge=1, le=32)

    @model_validator(mode="after")
    def resolve_db_path(self) -> Self:
        if self.db_path is None:
            self.db_path = self.volume_path / "db_example.db"
        elif not self.db_path.is_absolute():
            self.db_path = self.volume_path / self.db_path
        return self
