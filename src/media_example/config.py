from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class MediaConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="MEDIA_")

    schema_name: str = Field(default="media")
    pool_size: int = Field(default=4, ge=1, le=32)
    recent_limit: int = Field(default=50, ge=1, le=500)
    relay_batch: int = Field(default=100, ge=1, le=1000)
    relay_idle_sleep: float = Field(default=0.5, ge=0.05, le=10.0)
