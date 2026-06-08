from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class DbExampleLitestarConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="DB_EXAMPLE_LITESTAR_")

    schema_name: str = Field(default="db_example_litestar")
