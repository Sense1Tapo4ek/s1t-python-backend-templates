from pydantic_settings import BaseSettings, SettingsConfigDict


class MediaProcessingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDIA_PROCESSING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    worker_concurrency: int = 10
    thread_pool_size: int = 4
    process_pool_size: int = 2
    fake_work_seconds: float = 0.05
    transcode_iterations: int = 2_000_000
    join_ttl_seconds: int = 3600
    job_retries: int = 3
    job_timeout_seconds: int = 120
    metrics_port: int = 9100
