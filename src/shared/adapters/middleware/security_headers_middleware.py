"""Attach a baseline set of security headers to every HTTP response.

The middleware is config-driven (CSP string, HSTS toggle) so deployments
can tighten or loosen the defaults without touching code. ASGI-level so
it covers JSON APIs, HTML pages, SSE, and static files uniformly.
"""

from dataclasses import dataclass, field

from litestar.types import ASGIApp, Message, Receive, Scope, Send

# ASCII-only values encoded once at import time to avoid per-request allocation.
_STATIC_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-frame-options", b"DENY"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
)
_HSTS_VALUE = b"max-age=63072000; includeSubDomains"


@dataclass(slots=True)
class SecurityHeadersMiddleware:
    """ASGI middleware that injects security headers on http.response.start.

    The header list is built once per instance and appended verbatim — no
    per-request allocation beyond the small `extend()` call.
    """

    app: ASGIApp
    csp: str
    hsts_enabled: bool = False
    _headers: tuple[tuple[bytes, bytes], ...] = field(init=False)

    def __post_init__(self) -> None:
        headers: list[tuple[bytes, bytes]] = [
            (b"content-security-policy", self.csp.encode("ascii")),
            *_STATIC_HEADERS,
        ]
        if self.hsts_enabled:
            headers.append((b"strict-transport-security", _HSTS_VALUE))
        self._headers = tuple(headers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        injected = self._headers

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                # ASGI typing has `headers: Iterable[tuple[bytes, bytes]]`,
                # but every real server hands us a list. Build a fresh list
                # so we stay sound under both — cheap (~headers count items).
                existing = message.get("headers") or ()
                message["headers"] = [*existing, *injected]
            await send(message)

        await self.app(scope, receive, _send)
