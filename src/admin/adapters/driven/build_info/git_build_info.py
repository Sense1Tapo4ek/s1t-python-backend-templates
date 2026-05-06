"""Resolve git commit/branch/dirty for the running process.

Source priority:
1. Env vars (`GIT_COMMIT_SHA`, `GIT_BRANCH`, `GIT_DIRTY`) — set by CI / Docker build
2. `git` subprocess in current working directory — works in dev checkout
3. Fallback: `commit_sha="unknown"`, `branch=None`, `dirty=False`

Called ONCE at process startup (provider scope=APP). Result is immutable for
the lifetime of the process — that's the whole point of build info.
"""

import os
import subprocess
from datetime import UTC, datetime

from ....domain import BuildInfoVo

_GIT_TIMEOUT_S = 2.0


def resolve_build_info(app_name: str) -> BuildInfoVo:
    sha, branch, dirty = _from_env()
    if sha is None:
        sha, branch, dirty = _from_git()

    return BuildInfoVo(
        app_name=app_name,
        started_at=datetime.now(UTC),
        commit_sha=sha or "unknown",
        branch=branch,
        dirty=dirty,
    )


def _from_env() -> tuple[str | None, str | None, bool]:
    sha = os.environ.get("GIT_COMMIT_SHA", "").strip() or None
    if sha is None:
        return None, None, False
    branch = os.environ.get("GIT_BRANCH", "").strip() or None
    dirty = os.environ.get("GIT_DIRTY", "").strip().lower() in ("1", "true", "yes")
    return sha, branch, dirty


def _from_git() -> tuple[str | None, str | None, bool]:
    sha = _git("rev-parse", "HEAD")
    if sha is None:
        return None, None, False
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":  # detached
        branch = None
    status = _git("status", "--porcelain")
    dirty = bool(status)
    return sha, branch, dirty


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
