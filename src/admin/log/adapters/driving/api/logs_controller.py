from collections.abc import AsyncIterator
from pathlib import Path

import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, delete, get
from litestar.exceptions import ValidationException
from litestar.response import File, Stream
from litestar.status_codes import HTTP_200_OK

from auth.ports.driving import require_role
from shared.domain.auth import Role

from ....ports.driving.facades import LogsFacade
from ....ports.driving.schemas import (
    ClearLogsResponseSchema,
    LogFilterSchema,
    LogPageResponseSchema,
)

_log = structlog.get_logger(__name__)

# SSE-specific headers. `Cache-Control: no-cache` keeps proxies from replaying
# stale segments; `X-Accel-Buffering: no` disables nginx response buffering
# that would otherwise hold messages until the buffer fills.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

_INDEX_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"


class LogsPageController(Controller):
    path = "/admin/logs"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012

    @get("/", status_code=HTTP_200_OK)
    async def index(self) -> File:
        return File(
            path=str(_INDEX_HTML),
            media_type="text/html",
            content_disposition_type="inline",
        )


class LogsApiController(Controller):
    path = "/api/v1/admin/logs"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012

    @get("/", status_code=HTTP_200_OK)
    @inject
    async def api_logs(
        self,
        facade: FromDishka[LogsFacade],
        q: str | None = None,
        level: str | None = None,
        levels: list[str] | None = None,
    ) -> LogPageResponseSchema:
        schema = LogFilterSchema(q=q, min_level=level, levels=levels)
        response = await facade.render_log_page(schema)
        _log.info(
            "logs page served",
            q=q,
            min_level=level,
            levels=levels,
            entry_count=len(response.entries),
            cursor=response.cursor,
            has_more=response.has_more,
        )
        return response

    @get("/older", status_code=HTTP_200_OK)
    @inject
    async def api_older(
        self,
        facade: FromDishka[LogsFacade],
        cursor: int,
        q: str | None = None,
        level: str | None = None,
        levels: list[str] | None = None,
    ) -> LogPageResponseSchema:
        schema = LogFilterSchema(q=q, min_level=level, levels=levels)
        response = await facade.load_older_logs(cursor_id=cursor, schema=schema)
        _log.info(
            "logs older served",
            q=q,
            min_level=level,
            levels=levels,
            cursor=cursor,
            entry_count=len(response.entries),
            next_cursor=response.cursor,
            has_more=response.has_more,
        )
        return response

    @get("/stream", status_code=HTTP_200_OK)
    @inject
    async def api_stream(
        self,
        facade: FromDishka[LogsFacade],
        q: str | None = None,
        level: str | None = None,
        levels: list[str] | None = None,
    ) -> Stream:
        schema = LogFilterSchema(q=q, min_level=level, levels=levels, live_mode=True)
        # Validate DSL synchronously so DslSyntaxError surfaces as 400 BEFORE
        # the streaming response starts (otherwise the global handler can't
        # intercept and uvicorn raises "Exception caught after response started").
        facade.parse_filter(schema)
        _log.info("logs stream opened", q=q, min_level=level)

        async def generator() -> AsyncIterator[str]:
            try:
                async for entry in facade.stream_tail(schema):
                    yield f"data: {entry.model_dump_json()}\n\n"
            finally:
                _log.info("logs stream closed", q=q, min_level=level)

        return Stream(
            content=generator(),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )

    @delete("/", status_code=HTTP_200_OK)
    @inject
    async def api_clear(
        self,
        facade: FromDishka[LogsFacade],
        confirm: str | None = None,
    ) -> ClearLogsResponseSchema:
        if confirm != "yes-i-am-sure":
            raise ValidationException(
                "Provide ?confirm=yes-i-am-sure to wipe the log history.",
            )
        deleted = await facade.clear_logs()
        _log.warning("logs cleared via api", deleted=deleted)
        return ClearLogsResponseSchema(deleted=deleted)
