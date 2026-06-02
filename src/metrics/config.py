from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class MetricsConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="METRICS_")

    prom_endpoint_path: str = "/metrics"
    prom_endpoint_public: bool = False
    http_buckets: list[float] = Field(
        default_factory=lambda: [
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
        ]
    )
    multiproc_dir: Path | None = Field(default=None)

    @model_validator(mode="after")
    def resolve_multiproc_dir(self) -> Self:
        if self.multiproc_dir is None:
            self.multiproc_dir = self.volume_path / "prometheus"
        elif not self.multiproc_dir.is_absolute():
            self.multiproc_dir = self.volume_path / self.multiproc_dir
        return self
