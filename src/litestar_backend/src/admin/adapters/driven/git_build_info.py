import os
import subprocess

_GIT_TIMEOUT_S = 2.0


def resolve_build_meta() -> tuple[str | None, str | None, bool]:
    """Resolve (commit_sha, branch, dirty) from env, falling back to git.

    Primitives only -- the `BuildInfoVo` is assembled in the provider, so this
    driven adapter stays domain-blind.
    """
    sha, branch, dirty = _from_env()
    if sha is None:
        sha, branch, dirty = _from_git()
    return sha, branch, dirty


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
