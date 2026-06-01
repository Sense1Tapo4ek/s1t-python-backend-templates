from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class DbExampleLitestarConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="DB_EXAMPLE_LITESTAR_")

    db_path: Path | None = Field(default=None)

    @model_validator(mode="after")
    def resolve_db_path(self) -> Self:
        if self.db_path is None:
            self.db_path = self.volume_path / "db_example_litestar.db"
        elif not self.db_path.is_absolute():
            self.db_path = self.volume_path / self.db_path
        return self
