from html import escape as html_escape
from typing import Annotated
from urllib.parse import urlsplit

import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get, post
from litestar.connection import Request
from litestar.datastructures import Cookie
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Redirect, Response
from litestar.status_codes import HTTP_303_SEE_OTHER

from auth.config import ADMIN_COOKIE_NAME, MAX_TOKEN_LEN
from auth.ports.driving import AuthFacade
from shared.domain.auth import Role

from ....domain import BuildInfoVo

_log = structlog.get_logger(__name__)

LOGIN_PATH = "/admin/login"
DASHBOARD_PATH = "/admin/"

_LOGIN_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Login · {app_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/admin/logs/static/style.css" />
</head>
<body>
<div class="app app--page">
  <header class="topbar">
    <div class="brand">
      <span class="title">{app_name}</span>
      <span class="path">/<em>admin/login</em></span>
    </div>
  </header>

  <main class="login-main">
    <section class="panel">
      <h2>Sign in</h2>
      <p style="color:var(--ink-muted); font-size:12px; margin:0 0 20px 0;">
        Paste the admin bearer token to continue.
      </p>
      {error_block}
      <form method="post" action="{login_path}" autocomplete="off">
        <input type="hidden" name="next" value="{next_path}" />
        <div style="display:flex;flex-direction:column;gap:12px;">
          <label style="display:flex;flex-direction:column;gap:6px;font-size:12px;color:var(--ink-muted);">
            <span>token</span>
            <input
              type="password"
              name="token"
              required
              autofocus
              style="font-family:'JetBrains Mono',monospace;padding:10px 12px;border:1px solid var(--line);background:transparent;color:var(--sumi);font-size:14px;"
            />
          </label>
          <button
            type="submit"
            class="btn-link"
            style="justify-content:center;cursor:pointer;border:1px solid var(--line);"
          >enter <span class="arrow">→</span></button>
        </div>
      </form>
    </section>
  </main>

  <footer class="statusbar">
    <span class="grow"></span>
    <span>{app_name} · admin</span>
  </footer>
</div>
</body>
</html>"""

_ERROR_BLOCK = """<div style="border:1px solid var(--accent);padding:10px 12px;margin-bottom:16px;color:var(--accent-soft);background:var(--accent-tint);font-size:12px;">
  {message}
</div>"""


class LoginController(Controller):
    path = "/admin"

    @get("/login")
    @inject
    async def login_form(
        self,
        build: FromDishka[BuildInfoVo],
        next: str = DASHBOARD_PATH,
    ) -> Response[str]:
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

        # Same cap as the bearer middleware — refuse to feed an oversize
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
) -> Response[str]:
    # All values flow into HTML attributes / text via str.format(); escape so
    # `next_path="><script>...`, malicious `app_name`, or operator-supplied
    # error strings can never break out of the attribute / inject script.
    error_block = (
        _ERROR_BLOCK.format(message=html_escape(error)) if error else ""
    )
    html = _LOGIN_TEMPLATE.format(
        app_name=html_escape(app_name),
        login_path=LOGIN_PATH,
        next_path=html_escape(next_path, quote=True),
        error_block=error_block,
    )
    return Response(content=html, media_type="text/html", status_code=status_code)


def _safe_next(value: str) -> str:
    """Returns value only if it resolves to an /admin path with no host or
    scheme — prevents open redirect via percent-encoded netloc or
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
    # Drop attacker-controlled query/fragment — only the path is whitelisted.
    return path


def _is_https(request: Request) -> bool:
    """Trusts `X-Forwarded-Proto` from a reverse proxy. Without a
    TLS-terminating proxy that sets this header, the deployment must serve
    HTTPS directly — otherwise `admin_token` ships without `Secure`."""
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded:
        return forwarded.lower() == "https"
    return request.url.scheme == "https"
