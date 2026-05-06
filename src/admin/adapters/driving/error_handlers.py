"""Auth error handlers: HTML for browser requests under /admin/, JSON for
API callers — negotiated via `Accept` header."""

from urllib.parse import quote

from litestar import Response
from litestar.connection import Request
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from litestar.response import Redirect
from litestar.status_codes import (
    HTTP_303_SEE_OTHER,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

from .api.login_controller import LOGIN_PATH

_FORBIDDEN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><title>403 Forbidden</title>
<link rel="stylesheet" href="/admin/logs/static/style.css"/></head>
<body><div class="app app--page"><main class="login-main">
<section class="panel" style="text-align:center;max-width:480px;">
<h2>403 Forbidden</h2>
<p style="color:var(--ink-muted);font-size:13px;margin:14px 0 22px;">
You are signed in but your role does not grant access to this page.
</p>
<a class="btn-link primary" href="/admin/" style="justify-content:center;">return to dashboard <span class="arrow">→</span></a>
</section></main></div></body></html>"""


def not_authorized_handler(request: Request, exc: NotAuthorizedException) -> Response:
    """401 for API callers; 303 to /admin/login for browsers under /admin/*.

    The redirect carries the original path as ?next= so the user lands on
    the page they intended after signing in.
    """
    if request.url.path.startswith("/admin") and _wants_html(request):
        return _login_redirect(request)
    return Response(
        status_code=HTTP_401_UNAUTHORIZED,
        content={"detail": exc.detail},
    )


def permission_denied_handler(request: Request, exc: PermissionDeniedException) -> Response:
    """403 means authenticated but wrong role — redirecting to /admin/login
    would loop (the cookie is still valid). Render an HTML page for
    browsers, JSON detail for API callers.
    """
    if request.url.path.startswith("/admin") and _wants_html(request):
        return Response(
            content=_FORBIDDEN_HTML,
            media_type="text/html",
            status_code=HTTP_403_FORBIDDEN,
        )
    return Response(
        status_code=HTTP_403_FORBIDDEN,
        content={"detail": exc.detail},
    )


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    # Browsers send `text/html,...`; curl sends `*/*` or no header at all.
    # Under /admin/* we treat anything not explicitly JSON-only as a
    # browser navigation so login redirects / forbidden pages render.
    return not accept or "*/*" in accept or "text/html" in accept


def _login_redirect(request: Request) -> Redirect:
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    return Redirect(
        path=f"{LOGIN_PATH}?next={quote(next_path, safe='/?=&')}",
        status_code=HTTP_303_SEE_OTHER,
    )
