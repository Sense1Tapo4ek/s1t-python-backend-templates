from typing import Annotated
from urllib.parse import urlsplit

import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, Response, get, post
from litestar.connection import Request
from litestar.datastructures import Cookie
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Redirect, Template
from litestar.status_codes import HTTP_303_SEE_OTHER

from admin.config import LOGIN_PATH
from auth.config import ADMIN_COOKIE_NAME, MAX_TOKEN_LEN
from auth.ports.driving import AuthFacade
from shared.domain.auth import Role

from ....domain import BuildInfoVo

_log = structlog.get_logger(__name__)

DASHBOARD_PATH = "/admin/"


class LoginController(Controller):
    path = "/admin"

    @get("/login")
    @inject
    async def login_form(
        self,
        build: FromDishka[BuildInfoVo],
        next: str = DASHBOARD_PATH,
    ) -> Template:
        return _render(app_name=build.app_name, next_path=_safe_next(next))

    @post("/login", status_code=HTTP_303_SEE_OTHER)
    @inject
    async def login_submit(
        self,
        request: Request,
        facade: FromDishka[AuthFacade],
        build: FromDishka[BuildInfoVo],
        data: Annotated[
            dict[str, str],
            Body(media_type=RequestEncodingType.URL_ENCODED),
        ],
    ) -> Response:
        token = (data.get("token") or "").strip()
        next_path = _safe_next(data.get("next") or DASHBOARD_PATH)

        if not token:
            return _render(
                app_name=build.app_name,
                next_path=next_path,
                error="Token cannot be empty.",
                status_code=400,
            )

        # Same cap as the bearer middleware -- refuse to feed an oversize
        # value into `secrets.compare_digest`. Treated as invalid (no
        # length leak) rather than a separate error to keep responses
        # uniform.
        if len(token) > MAX_TOKEN_LEN:
            _log.warning("login rejected", reason="token too long")
            return _render(
                app_name=build.app_name,
                next_path=next_path,
                error="Invalid token.",
                status_code=401,
            )

        principal = await facade.authenticate(token)
        if principal is None or principal.role != Role.ADMIN:
            _log.warning(
                "login rejected",
                reason="invalid token" if principal is None else "insufficient role",
            )
            return _render(
                app_name=build.app_name,
                next_path=next_path,
                error="Invalid token.",
                status_code=401,
            )

        _log.info("login accepted", token_id=principal.token_id)
        return Redirect(
            path=next_path,
            status_code=HTTP_303_SEE_OTHER,
            cookies=[
                Cookie(
                    key=ADMIN_COOKIE_NAME,
                    value=token,
                    path="/",
                    httponly=True,
                    samesite="strict",
                    secure=_is_https(request),
                ),
            ],
        )

    @post("/logout", status_code=HTTP_303_SEE_OTHER)
    async def logout(self, request: Request) -> Response:
        return Redirect(
            path=LOGIN_PATH,
            status_code=HTTP_303_SEE_OTHER,
            cookies=[
                Cookie(
                    key=ADMIN_COOKIE_NAME,
                    value="",
                    path="/",
                    httponly=True,
                    samesite="strict",
                    secure=_is_https(request),
                    max_age=0,
                ),
            ],
        )


def _render(
    *,
    app_name: str,
    next_path: str,
    error: str | None = None,
    status_code: int = 200,
) -> Template:
    return Template(
        template_name="admin/login.html",
        context={
            "app_name": app_name,
            "login_path": LOGIN_PATH,
            "next_path": next_path,
            "error": error,
        },
        status_code=status_code,
    )


def _safe_next(value: str) -> str:
    """Returns value only if it resolves to an /admin path with no host or
    scheme -- prevents open redirect via percent-encoded netloc or
    dot-segment smuggling."""
    if not value:
        return DASHBOARD_PATH
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return DASHBOARD_PATH
    path = parts.path
    if not path.startswith("/admin"):
        return DASHBOARD_PATH
    # Reject backslashes (Windows-style) and dot-segments.
    if "\\" in path or "/.." in path or path.endswith("/.."):
        return DASHBOARD_PATH
    # Drop attacker-controlled query/fragment -- only the path is whitelisted.
    return path


def _is_https(request: Request) -> bool:
    """Trusts `X-Forwarded-Proto` from a reverse proxy. Without a
    TLS-terminating proxy that sets this header, the deployment must serve
    HTTPS directly -- otherwise `admin_token` ships without `Secure`."""
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded:
        return forwarded.lower() == "https"
    return request.url.scheme == "https"
