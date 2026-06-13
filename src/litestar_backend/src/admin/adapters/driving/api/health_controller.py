import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE

from shared.adapters.driven.readiness import ReadinessProbe
from shared.adapters.openapi import error_responses
from shared.config import BaseAppConfig

from ....ports.driving import BuildInfoVo

_log = structlog.get_logger(__name__)


def _probe_log_dir(config: BaseAppConfig) -> str:
    # A bare is_dir() passes on a read-only mount where every log write then
    # fails; probe with a real create+unlink.
    try:
        probe = config.log_dir / ".readiness_probe"
        probe.touch()
        probe.unlink()
    except Exception:  # probe degrades to "down" on any failure
        return "down"
    return "up"


class HealthController(Controller):
    """Two-tier health: /health is always-200 liveness (the process is up);
    /health/ready is the dependency view -- log dir writable plus Postgres and
    Valkey reachable -- and returns 503 with a per-dependency `checks` map when
    any is down."""

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
        probe: FromDishka[ReadinessProbe],
    ) -> dict[str, object]:
        """Readiness: log dir writable + Postgres and Valkey reachable.

        Returns 503 with a per-dependency `checks` map when any hard dependency
        is down; the process itself stays live on /health.
        """
        checks: dict[str, str] = {"log_dir": _probe_log_dir(config)}
        report = await probe.check()
        checks.update(report.checks)
        ok = report.ok and checks["log_dir"] == "up"
        if not ok:
            _log.warning("readiness degraded", checks=checks)
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail="degraded",
                extra=checks,
            )
        return {"status": "ready", "checks": checks}

    @get("/ping", sync_to_thread=False, summary="Ping")
    def ping(self) -> dict[str, str]:
        """Minimal liveness check returning a static pong."""
        return {"message": "pong"}
