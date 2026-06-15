from uuid import uuid4

import structlog
from litestar.types import ASGIApp, Message, Receive, Scope, Send

_TRACE_HEADER = b"x-trace-id"
_REQUEST_ID_HEADER = b"x-request-id"
# Inbound precedence: x-trace-id wins, x-request-id is the accepted alias.
_INBOUND_HEADERS = (_TRACE_HEADER, _REQUEST_ID_HEADER)


class TraceIdMiddleware:
    """Bind X-Trace-Id (incoming or generated) to structlog contextvars; echo on response.

    Inbound id is read from X-Trace-Id, else the X-Request-Id alias, else
    generated. The chosen id is always echoed on the response as X-Trace-Id.

    Snitchbot has its own request_context id (installed via
    `snitchbot.integrations.litestar.install`), intentionally not unified.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        trace_id = _read_trace_header(scope) or uuid4().hex[:16]
        token = structlog.contextvars.bind_contextvars(trace_id=trace_id)

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((_TRACE_HEADER, trace_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self._app(scope, receive, _send)
        finally:
            structlog.contextvars.reset_contextvars(**token)


def _read_trace_header(scope: Scope) -> str | None:
    seen: dict[bytes, str | None] = {}
    for name, value in scope.get("headers", ()):
        key = name.lower()
        if key in _INBOUND_HEADERS and key not in seen:
            try:
                seen[key] = value.decode("ascii").strip()
            except UnicodeDecodeError:
                seen[key] = None
    for header in _INBOUND_HEADERS:
        if header in seen:
            return seen[header]
    return None
