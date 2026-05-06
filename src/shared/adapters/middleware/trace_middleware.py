from uuid import uuid4

import structlog
from litestar.types import ASGIApp, Message, Receive, Scope, Send

_TRACE_HEADER = b"x-trace-id"


class TraceIdMiddleware:
    """Generate or honor a request trace id and bind it to structlog contextvars.

    On request:
      - Read X-Trace-Id from incoming headers if present, else uuid4().hex[:16].
      - Bind trace_id to structlog contextvars so every downstream log record
        carries it via merge_contextvars.

    On response:
      - Echo the trace id back as X-Trace-Id for client correlation.

    Snitchbot has its own request_context (trace_id, http_method, http_path,
    client_ip) installed via `snitchbot.integrations.litestar.install(app)` —
    that's a separate id used in snitchbot alerts, intentionally not unified
    with this one.
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
    for name, value in scope.get("headers", ()):
        if name.lower() == _TRACE_HEADER:
            try:
                return value.decode("ascii").strip()
            except UnicodeDecodeError:
                return None
    return None
