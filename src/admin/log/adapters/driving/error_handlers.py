"""HTTP exception handlers specific to the admin/log context."""

import structlog
from litestar import Response
from litestar.connection import Request
from litestar.status_codes import HTTP_400_BAD_REQUEST

from ...domain import DslSyntaxError, InvalidLogFilterError

_log = structlog.get_logger("root.errors")


def dsl_syntax_handler(_req: Request, exc: DslSyntaxError) -> Response:
    """Returns position + reason verbatim; bypasses the generic DomainError
    409 handler."""
    _log.warning(
        "dsl rejected",
        position=exc.position,
        reason=exc.reason,
    )
    return Response(
        status_code=HTTP_400_BAD_REQUEST,
        content={"position": exc.position, "reason": exc.reason},
    )


def invalid_log_filter_handler(
    _req: Request, exc: InvalidLogFilterError
) -> Response:
    """Returns structured field/reason; bypasses the generic DomainError
    409 handler."""
    _log.warning(
        "log filter rejected",
        field=exc.field,
        reason=exc.reason,
    )
    return Response(
        status_code=HTTP_400_BAD_REQUEST,
        content={"field": exc.field, "reason": exc.reason},
    )
