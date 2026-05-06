from collections.abc import Callable

from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from litestar.handlers.base import BaseRouteHandler

from shared.domain.auth import Principal, Role


def require_role(*roles: Role) -> Callable[[ASGIConnection, BaseRouteHandler], None]:
    """UNKNOWN role → 401 (login redirect expected upstream); authenticated
    but wrong role → 403."""
    role_set = frozenset(roles)
    role_names = tuple(r.value for r in roles)

    def guard(connection: ASGIConnection, _handler: BaseRouteHandler) -> None:
        user: Principal | None = getattr(connection, "user", None)
        if user is None or user.role == Role.UNKNOWN:
            raise NotAuthorizedException(detail="authentication required")
        if user.role not in role_set:
            raise PermissionDeniedException(
                detail=f"requires one of: {', '.join(role_names)}",
            )

    return guard
