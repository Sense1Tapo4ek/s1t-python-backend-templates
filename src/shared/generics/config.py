from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

SRC_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SRC_DIR.parent


def _resolve_env_file() -> Path | None:
    """Locate `.env` at instance creation, not class definition.

    Why: child configs (`AuthConfig`, `AdminLogConfig`) snapshot
    `model_config` from the base when they declare their own — so a test-time
    `monkeypatch.setitem(BaseAppConfig.model_config, ...)` can't reach them.
    Resolving via a function keeps a single point that tests override with
    `monkeypatch.setattr`.
    """
    for directory in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
        env_path = directory / ".env"
        if env_path.is_file():
            return env_path
    return None


class GenericConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("_env_file", _resolve_env_file())
        super().__init__(**kwargs)

    @property
    def src_dir(self) -> Path:
        return SRC_DIR

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT
