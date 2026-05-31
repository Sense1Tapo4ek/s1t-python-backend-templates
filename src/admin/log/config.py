from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig
from shared.generics.config import PROJECT_ROOT

YOYO_MIGRATION_TABLE = "_yoyo_admin_log"

# Migrations directory path. Owned by lifespan for yoyo execution.
log_migrations_path: Path = PROJECT_ROOT / "migrations" / "admin_log"

# Database path for log persistence. Owned by the log sink process.
log_db_path: Path = PROJECT_ROOT / "storage" / "logs" / "admin_logs.db"


class AdminLogConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="LOG_")

    # Path to the JSONL file the admin UI reads. Written by the structlog
    # WatchedFileHandler; rotated externally (logrotate / docker). When
    # unset it defaults to <log_dir>/app.jsonl (see resolve_log_file_path).
    log_file_path: Path | None = Field(default=None)

    # Initial history page size (tail -N).
    log_tail_lines: int = Field(default=200, ge=1, le=5000)

    # "Load more" page size (read_before).
    log_load_more_lines: int = Field(default=200, ge=1, le=5000)

    # Follow poll interval for the live SSE tail.
    log_follow_poll_ms: int = Field(default=250, ge=50, le=5000)

    # Write-side line cap; reader skips lines exceeding this as malformed.
    log_max_line_bytes: int = Field(default=64 * 1024, ge=1024)

    # Single knob for query page sizes (initial render + "load older").
    # Field constraints replace the old runtime-clamp `log_max_limit`.
    log_page_size: int = Field(default=200, ge=1, le=1000)

    # Migrations directory path. Owned by lifespan for yoyo execution.
    log_migrations_path: Path = Field(
        default=PROJECT_ROOT / "migrations" / "admin_log",
    )

    # Database path for log persistence. Owned by the log sink process.
    log_db_path: Path = Field(
        default=PROJECT_ROOT / "storage" / "logs" / "admin_logs.db",
    )

    @model_validator(mode="after")
    def resolve_log_file_path(self) -> Self:
        if self.log_file_path is None:
            self.log_file_path = self.log_dir / "app.jsonl"
        elif not self.log_file_path.is_absolute():
            self.log_file_path = self.log_dir / self.log_file_path
        return self
