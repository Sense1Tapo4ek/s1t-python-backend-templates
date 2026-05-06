import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE

from shared.adapters.driven.db import SQLiteConnection

from ....domain import BuildInfoVo

_log = structlog.get_logger(__name__)


class HealthController(Controller):
    """Two-tier health: /health is always-200 liveness; /health/ready probes
    the SQLite reader pool and returns 503 on failure."""

    path = ""

    @get("/health")
    @inject
    async def health(self, build: FromDishka[BuildInfoVo]) -> dict[str, str | bool]:
        return {
            "status": "ok",
            "app": build.app_name,
            "commit": build.commit_sha,
            "branch": build.branch or "",
            "dirty": build.dirty,
            "started_at": build.started_at.isoformat(),
        }

    @get("/health/ready")
    @inject
    async def ready(
        self,
        connection: FromDishka[SQLiteConnection],
    ) -> dict[str, str]:
        # Exercises connection acquisition without touching app tables;
        # any exception becomes 503 to signal readiness failure.
        try:
            async with connection.read() as db, db.execute("SELECT 1") as cur:
                await cur.fetchone()
        except Exception as exc:
            _log.exception("readiness check failed", error_type=type(exc).__name__)
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail="not ready",
            ) from exc
        return {"status": "ready"}

    @get("/ping", sync_to_thread=False)
    def ping(self) -> dict[str, str]:
        return {"message": "pong"}
