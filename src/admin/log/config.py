from pathlib import Path

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig
from shared.generics.config import PROJECT_ROOT

YOYO_MIGRATION_TABLE = "_yoyo_admin_log"


class AdminLogConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="LOG_")

    log_retention_days: int = Field(default=7, ge=1)
    log_batch_size: int = Field(default=100, ge=1)
    log_batch_timeout_ms: int = Field(default=100, ge=10)
    log_sse_queue_size: int = Field(default=100, ge=10)
    log_cleanup_interval_hours: int = Field(default=24, ge=1)
    log_tail_size: int = Field(default=200, ge=1)
    log_history_chunk: int = Field(default=200, ge=1)
    log_db_reader_count: int = Field(default=4, ge=1)
    # Upper bound on a single SQL query's LIMIT. Caller-side configs
    # (log_tail_size, log_history_chunk) are bounded by this — a misconfig
    # asking for a million-row tail is rejected at builder time rather than
    # materialising a giant cursor.
    log_max_limit: int = Field(default=5000, ge=1)
    # SSE tail polls the log table for rows past the last cursor. Each poll
    # acquires a reader from the pool, so a short interval x many subscribers
    # starves the pool. Cost of latency is bounded by this value.
    log_stream_poll_interval_s: float = Field(default=3.0, ge=0.1)
    log_migrations_path: Path = Field(
        default=PROJECT_ROOT / "migrations" / "admin_log",
    )
    # Bundled with the context; root serves it via static_files_router.
    log_static_path: Path = Field(
        default=PROJECT_ROOT / "src" / "admin" / "log" / "adapters" / "driving" / "static",
    )

    @property
    def log_db_path(self) -> Path:
        return self.log_dir / "admin_logs.db"
