import re

import structlog
from litestar.connection import ASGIConnection
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult

from shared.domain.auth import Principal, Role
from shared.generics.errors import PortError

from ..config import ADMIN_COOKIE_NAME, MAX_TOKEN_LEN
from ..ports.driving import AuthFacade

_log = structlog.get_logger(__name__)
_BEARER_RE = re.compile(r"^Bearer\s+(.+)$", re.IGNORECASE)
_COOKIE_PATH_PREFIXES = ("/admin", "/api/v1/admin")
_ANON = Principal(role=Role.UNKNOWN, token_id="anonymous")


class AuthMiddleware(AbstractAuthenticationMiddleware):
    """Reads bearer token from `Authorization` header or `admin_token` cookie.

    Never raises. Every connection ends up with a `Principal`:
    - Valid token -> resolved Principal (e.g., Role.ADMIN)
    - Missing/invalid/empty token -> `Principal(role=UNKNOWN, ...)`

    Authorization decisions live in `require_role` guards on protected
    controllers. Public endpoints (/health, /ping, /admin/login) just
    don't declare a guard.
    """

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        token = _extract_token(connection)
        if token is None:
            return AuthenticationResult(user=_ANON, auth=_ANON.token_id)

        # The facade is resolved once at lifespan startup and stashed on
        # app.state -- middleware reads the prepared instance instead of
        # walking the DI container per request.
        facade: AuthFacade = connection.app.state.auth_facade
        try:
            principal = await facade.authenticate(token)
        except PortError:
            # Denylist (Valkey) unreachable -> fail closed: a JWT we cannot
            # check for revocation is treated as unauthenticated. The static
            # admin path never reaches the denylist (shape gate), so this only
            # degrades JWT auth during a Valkey outage.
            _log.warning("auth rejected", reason="denylist unavailable")
            return AuthenticationResult(user=_ANON, auth=_ANON.token_id)

        if principal is None:
            _log.warning("auth rejected", reason="invalid token")
            return AuthenticationResult(user=_ANON, auth=_ANON.token_id)

        return AuthenticationResult(user=principal, auth=principal.token_id)


def _extract_token(connection: ASGIConnection) -> str | None:
    # Reject oversize inputs before touching them -- `secrets.compare_digest`
    # encodes the candidate to bytes, so an attacker-controlled multi-MB
    # value would burn memory/CPU on every request.
    auth_header = connection.headers.get("authorization")
    if (
        auth_header
        and len(auth_header) <= MAX_TOKEN_LEN + 16
        and (match := _BEARER_RE.match(auth_header))
    ):
        token = match.group(1).strip()
        if token and len(token) <= MAX_TOKEN_LEN:
            return token

    # The admin cookie authenticates ONLY the admin surface. Everything else
    # requires a bearer credential -- otherwise a browser holding the cookie
    # would silently authenticate CSRF-excluded API endpoints.
    path = connection.url.path
    if path.startswith(_COOKIE_PATH_PREFIXES):
        cookie_token = connection.cookies.get(ADMIN_COOKIE_NAME)
        if cookie_token and len(cookie_token) <= MAX_TOKEN_LEN:
            cookie_token = cookie_token.strip()
            if cookie_token:
                return cookie_token

    return None
