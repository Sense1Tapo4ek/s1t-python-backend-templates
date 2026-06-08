import time

import structlog
from litestar.types import ASGIApp, Message, Receive, Scope, Send

_logger = structlog.get_logger("access")

_FORWARDED_FOR = b"x-forwarded-for"
_USER_AGENT = b"user-agent"


class AccessLogMiddleware:
    """Lightweight ASGI middleware that emits one structured access record per HTTP request.

    Body content is intentionally NOT logged (PII risk); only metadata.
    `trace_id` is supplied automatically via structlog contextvars set by
    `TraceIdMiddleware` (see `merge_contextvars` in `shared/logging.py`),
    so callers don't need to pass it through here.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        status_code = 500
        started = time.perf_counter()

        async def _send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, _send)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            _logger.info(
                "request",
                method=scope.get("method"),
                http_path=scope.get("path"),
                query=_decode_query(scope),
                status=status_code,
                duration_ms=duration_ms,
                client_ip=_client_ip(scope),
                user_agent=_user_agent(scope),
                user=_user_token_id(scope),
            )


def _decode_query(scope: Scope) -> str | None:
    raw = scope.get("query_string") or b""
    if not raw:
        return None
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _header(scope: Scope, name: bytes) -> str | None:
    for header_name, value in scope.get("headers", ()):
        if header_name.lower() == name:
            try:
                return value.decode("latin-1")
            except UnicodeDecodeError:
                return None
    return None


def _client_ip(scope: Scope) -> str:
    forwarded = _header(scope, _FORWARDED_FOR)
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


def _user_agent(scope: Scope) -> str | None:
    return _header(scope, _USER_AGENT)


def _user_token_id(scope: Scope) -> str | None:
    """Return the authenticated principal's token_id, or None for anonymous.

    Litestar's AbstractAuthenticationMiddleware places `Principal` into
    `scope["user"]`. We read it via attribute access to stay decoupled from
    the auth context (the value is duck-typed: anything with a `.token_id`).
    """
    principal = scope.get("user")
    if principal is None:
        return None
    return getattr(principal, "token_id", None)
