from pydantic_settings import BaseSettings, SettingsConfigDict


class MediaProcessingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDIA_PROCESSING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    fan_out: int = 3
    worker_concurrency: int = 10
    thread_pool_size: int = 4
    process_pool_size: int = 2
    fake_work_seconds: float = 0.05
    transcode_iterations: int = 2_000_000
    join_ttl_seconds: int = 3600
