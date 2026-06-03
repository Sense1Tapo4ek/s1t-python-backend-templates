from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class DbExampleSdddConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="DB_EXAMPLE_SDDD_")

    schema_name: str = Field(default="db_example_sddd")
    pool_size: int = Field(default=4, ge=1, le=32)
