from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppConfig


class AdminLogConfig(BaseAppConfig):
    model_config = SettingsConfigDict(env_prefix="LOG_")

    # Path to the JSONL file the admin UI reads. Written by the structlog
    # WatchedFileHandler; rotated externally (logrotate / docker). When
    # unset it defaults to <log_dir>/app.jsonl (see resolve_log_file_path).
    file_path: Path | None = Field(default=None)

    # Initial history page size (tail -N).
    tail_lines: int = Field(default=200, ge=1, le=5000)

    # "Load more" page size (read_before).
    load_more_lines: int = Field(default=200, ge=1, le=5000)

    # Follow poll interval for the live SSE tail.
    follow_poll_ms: int = Field(default=250, ge=50, le=5000)

    # Write-side line cap; reader skips lines exceeding this as malformed.
    max_line_bytes: int = Field(default=64 * 1024, ge=1024)

    @model_validator(mode="after")
    def resolve_log_file_path(self) -> Self:
        if self.file_path is None:
            self.file_path = self.log_dir / "app.jsonl"
        elif not self.file_path.is_absolute():
            self.file_path = self.log_dir / self.file_path
        return self
