from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class MetricsConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="METRICS_")

    enabled: bool = True
    prom_endpoint_path: str = "/metrics"
    prom_endpoint_public: bool = False
    publish_interval_s: float = Field(default=5.0, ge=1.0)
    key_prefix: str = "metrics:"
    key_ttl_s: int = Field(default=30, ge=5)
    http_buckets: list[float] = Field(
        default_factory=lambda: [
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
        ]
    )
    process_buckets: list[float] = Field(
        default_factory=lambda: [
            0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0
        ]
    )
