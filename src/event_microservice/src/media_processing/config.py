from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .domain import JobKind


class MediaProcessingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDIA_PROCESSING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    fan_out: int = len(JobKind)
    worker_concurrency: int = 10
    thread_pool_size: int = 4
    process_pool_size: int = 2
    fake_work_seconds: float = 0.05
    transcode_iterations: int = 2_000_000
    join_ttl_seconds: int = 3600
    job_retries: int = 3
    job_timeout_seconds: int = 120

    @model_validator(mode="after")
    def _fan_out_matches_job_kinds(self) -> "MediaProcessingConfig":
        if self.fan_out != len(JobKind):
            raise ValueError(
                f"fan_out must equal the number of JobKinds ({len(JobKind)}), got {self.fan_out}"
            )
        return self
