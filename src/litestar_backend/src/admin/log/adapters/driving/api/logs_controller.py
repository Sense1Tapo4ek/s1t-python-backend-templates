from collections.abc import AsyncIterator

import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.exceptions import ValidationException
from litestar.response import ServerSentEvent, Template
from litestar.status_codes import HTTP_200_OK

from auth.ports.driving import ADMIN_SECURITY, require_role
from shared.adapters.openapi import error_responses
from shared.domain.auth import Role

from ....config import AdminLogConfig
from ....ports.driving import (
    LogPageResponseSchema,
    LogsFacade,
    decode_cursor,
    encode_cursor,
)

_log = structlog.get_logger(__name__)

# `Cache-Control: no-cache` keeps proxies from replaying stale segments;
# `X-Accel-Buffering: no` disables nginx response buffering that would hold
# messages until the buffer fills.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


class LogsPageController(Controller):
    path = "/admin/logs"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012
    security = ADMIN_SECURITY
    tags = ["Admin UI"]  # noqa: RUF012

    @get("/", status_code=HTTP_200_OK)
    async def index(self) -> Template:
        """Render the admin log-viewer HTML page."""
        return Template(template_name="admin/log/index.html")


class LogsApiController(Controller):
    path = "/api/v1/admin/logs"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012
    security = ADMIN_SECURITY
    tags = ["Admin Logs"]  # noqa: RUF012

    @get("/", status_code=HTTP_200_OK,
         summary="Latest log page", responses=error_responses(401, 403))
    @inject
    async def api_logs(
        self,
        facade: FromDishka[LogsFacade],
        config: FromDishka[AdminLogConfig],
    ) -> LogPageResponseSchema:
        """Return the newest page of log entries plus a cursor for older pages."""
        entries, cursor = await facade.render_log_page(config.tail_lines)
        _log.info("logs page served", entry_count=len(entries))
        return LogPageResponseSchema(
            entries=entries,
            cursor=encode_cursor(cursor),
        )

    @get("/older", status_code=HTTP_200_OK,
         summary="Older log page (cursor)", responses=error_responses(400, 401, 403))
    @inject
    async def api_older(
        self,
        facade: FromDishka[LogsFacade],
        config: FromDishka[AdminLogConfig],
        cursor: str,
    ) -> LogPageResponseSchema:
        """Return an older page of log entries from the given opaque cursor."""
        try:
            decoded = decode_cursor(cursor)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc
        entries, next_cursor = await facade.load_older_logs(
            decoded,
            config.load_more_lines,
        )
        _log.info("logs older served", entry_count=len(entries))
        return LogPageResponseSchema(
            entries=entries,
            cursor=encode_cursor(next_cursor),
        )

    @get("/stream", status_code=HTTP_200_OK,
         summary="Live log tail (SSE)", responses=error_responses(401, 403))
    @inject
    async def api_stream(
        self,
        facade: FromDishka[LogsFacade],
        config: FromDishka[AdminLogConfig],
    ) -> ServerSentEvent:
        """Tail the log file live as ``text/event-stream``.

        Each event carries one log entry serialized as JSON.
        """
        # Synchronous validation BEFORE building the response: headers are
        # already flushed once the generator starts, so any error raised
        # inside it cannot become a 4xx/5xx (spec 10.5 G).
        poll_ms = config.follow_poll_ms
        if poll_ms <= 0:
            raise ValidationException("LOG_FOLLOW_POLL_MS must be positive")
        _log.info("logs stream opened")

        async def generator() -> AsyncIterator[str]:
            try:
                async for entry in facade.stream_tail(poll_ms):
                    yield entry.model_dump_json()
            finally:
                _log.info("logs stream closed")

        return ServerSentEvent(generator(), headers=_SSE_HEADERS)
