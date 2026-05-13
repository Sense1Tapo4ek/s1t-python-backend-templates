"""S-DDD layer-error to HTTP mappers (Domain 409, App 422, Port 503, Adapter 500).

`str(exc)` is logged for diagnosis but never sent over the wire —
messages may carry internal details. Context-specific handlers
registered against concrete subtypes run first and bypass these.
"""

import structlog
from litestar import Response
from litestar.connection import Request
from litestar.exceptions import ValidationException
from litestar.status_codes import (
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from shared.generics.errors import AdapterError, AppError, DomainError, PortError

_log = structlog.get_logger("root.errors")


def domain_error_handler(_req: Request, exc: DomainError) -> Response:
    _log.warning(
        "domain error",
        error_type=type(exc).__name__,
        message=str(exc),
    )
    return Response(status_code=HTTP_409_CONFLICT, content={"detail": "Conflict"})


def app_error_handler(_req: Request, exc: AppError) -> Response:
    _log.warning(
        "app error",
        error_type=type(exc).__name__,
        message=str(exc),
    )
    return Response(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Unprocessable"},
    )


def port_error_handler(_req: Request, exc: PortError) -> Response:
    _log.exception("port error", error_type=type(exc).__name__)
    return Response(
        status_code=HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Service unavailable"},
    )


def adapter_error_handler(_req: Request, exc: AdapterError) -> Response:
    _log.exception("adapter error", error_type=type(exc).__name__)
    return Response(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def validation_exception_handler(
    _req: Request,
    exc: ValidationException,
) -> Response:
    """Preserve `extra` (per-field violation list) on its way to the client.

    The generic HTTPException catch-all flattens to `{"detail": ...}` and
    drops `extra`, leaving callers without the field-level diagnostics
    Pydantic produces. Registering this before the HTTPException entry in
    the handler map makes Litestar pick it for ValidationException.
    """
    return Response(
        status_code=exc.status_code,
        content={"detail": exc.detail, "extra": exc.extra},
    )


def fallback_500_handler(_req: Request, exc: Exception) -> Response:
    """Catch-all for unexpected exceptions.

    Without this, an exception not covered by a registered handler would
    surface a Litestar-rendered 500 that includes the traceback when
    `debug=True`. We force a generic body and log the full traceback
    server-side regardless of debug state.
    """
    _log.exception("unhandled exception", error_type=type(exc).__name__)
    return Response(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
