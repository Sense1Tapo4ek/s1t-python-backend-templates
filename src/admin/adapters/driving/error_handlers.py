from urllib.parse import quote

from litestar import Response
from litestar.connection import Request
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from litestar.response import Redirect, Template
from litestar.status_codes import (
    HTTP_303_SEE_OTHER,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

from .api.login_controller import LOGIN_PATH


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
    """403 means authenticated but wrong role -- redirecting to /admin/login
    would loop (the cookie is still valid). Render an HTML page for
    browsers, JSON detail for API callers.
    """
    if request.url.path.startswith("/admin") and _wants_html(request):
        return Template(
            template_name="admin/forbidden.html",
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
