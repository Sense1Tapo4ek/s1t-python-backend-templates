from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class MediaConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="MEDIA_")

    schema_name: str = Field(default="media")
    pool_size: int = Field(default=4, ge=1, le=32)
    relay_batch: int = Field(default=100, ge=1, le=1000)
    relay_idle_sleep: float = Field(default=0.5, ge=0.05, le=10.0)
    status_batch: int = Field(default=100, ge=1, le=1000)
    status_block_ms: int = Field(default=1000, ge=100, le=30000)
    status_claim_idle_ms: int = Field(default=60_000, ge=0)
    feed_max_connections: int = Field(default=100, ge=1, le=10_000)
    feed_heartbeat_seconds: float = Field(default=15.0, ge=1.0, le=300.0)
    idempotency_ttl_seconds: int = Field(default=86_400, ge=60)
    idempotency_purge_interval_seconds: float = Field(default=3600.0, ge=60.0)
