from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class BuildInfoVo:
    """`commit_sha` is "unknown" when neither env vars nor git subprocess
    are available."""

    app_name: str
    started_at: datetime
    commit_sha: str
    branch: str | None
    dirty: bool
