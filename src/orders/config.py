from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class OrdersConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="ORDERS_")

    schema_name: str = Field(default="orders")
    pool_size: int = Field(default=4, ge=1, le=32)
    recent_limit: int = Field(default=50, ge=1, le=500)
