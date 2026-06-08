import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE

from shared.adapters.openapi import error_responses
from shared.config import BaseAppConfig

from ....ports.driving import BuildInfoVo

_log = structlog.get_logger(__name__)


class HealthController(Controller):
    """Two-tier health: /health is always-200 liveness; /health/ready is a
    liveness-plus-config check (config resolves and the log directory is
    writable) and returns 503 on failure. The log path is a plain file, so
    there is no DB pool to probe.

    Writability is probed on log_dir; an absolute LOG_FILE_PATH pointing
    outside it is not covered."""

    path = ""
    tags = ["Health"]  # noqa: RUF012

    @get("/health", summary="Liveness")
    @inject
    async def health(self, build: FromDishka[BuildInfoVo]) -> dict[str, str | bool]:
        """Always-200 liveness probe returning build/version metadata."""
        return {
            "status": "ok",
            "app": build.app_name,
            "commit": build.commit_sha,
            "branch": build.branch or "",
            "dirty": build.dirty,
            "started_at": build.started_at.isoformat(),
        }

    @get("/health/ready", summary="Readiness", responses=error_responses(503))
    @inject
    async def ready(
        self,
        config: FromDishka[BaseAppConfig],
    ) -> dict[str, str]:
        """Readiness probe: config resolves and the log directory is writable.

        Returns 503 when the writability probe fails.
        """
        # Readiness = config resolved + the log directory is actually
        # writable, so the structlog file handler can append. A bare is_dir()
        # passes on a read-only mount where every log write then fails; probe
        # with a real create+unlink. Any failure becomes 503.
        try:
            probe = config.log_dir / ".readiness_probe"
            probe.touch()
            probe.unlink()
        except Exception as exc:
            _log.exception("readiness check failed", error_type=type(exc).__name__)
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail="not ready",
            ) from exc
        return {"status": "ready"}

    @get("/ping", sync_to_thread=False, summary="Ping")
    def ping(self) -> dict[str, str]:
        """Minimal liveness check returning a static pong."""
        return {"message": "pong"}
