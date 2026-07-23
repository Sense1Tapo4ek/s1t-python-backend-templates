import re

import structlog
from litestar.connection import Request
from litestar.plugins.problem_details import ProblemDetailsException
from litestar.response import Response
from litestar.status_codes import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from shared.generics.errors import AppError, DomainError, PortError

_log = structlog.get_logger("root.errors")
_TYPE_BASE = "urn:litestar-base:error"


def _type_uri(exc: Exception) -> str:
    # FakeAlreadyPaid -> urn:litestar-base:error:fake-already-paid
    slug = re.sub(r"(?<!^)(?=[A-Z])", "-", type(exc).__name__).lower()
    return f"{_TYPE_BASE}:{slug}"


def domain_to_problem(exc: DomainError) -> ProblemDetailsException:
    _log.warning("domain error", error_type=type(exc).__name__, message=str(exc))
    return ProblemDetailsException(
        status_code=HTTP_409_CONFLICT,
        title="Conflict",
        detail=str(exc),
        type_=_type_uri(exc),
    )


def app_to_problem(exc: AppError) -> ProblemDetailsException:
    _log.warning("app error", error_type=type(exc).__name__, message=str(exc))
    return ProblemDetailsException(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail=str(exc),
        type_=_type_uri(exc),
    )


def jwt_disabled_to_problem(exc: Exception) -> ProblemDetailsException:
    _log.warning("jwt disabled", error_type=type(exc).__name__, message=str(exc))
    return ProblemDetailsException(
        status_code=HTTP_503_SERVICE_UNAVAILABLE,
        title="JWT Not Configured",
        detail=str(exc),
        type_=f"{_TYPE_BASE}:jwt-disabled",
    )


def not_found_to_problem(exc: Exception) -> ProblemDetailsException:
    _log.warning("not found", error_type=type(exc).__name__, message=str(exc))
    return ProblemDetailsException(
        status_code=HTTP_404_NOT_FOUND,
        title="Not Found",
        detail=str(exc),
        type_=_type_uri(exc),
    )


def port_to_problem(exc: PortError) -> ProblemDetailsException:
    # 5xx: log full context, expose nothing internal.
    _log.error("port error", error_type=type(exc).__name__, exc_info=exc)
    return ProblemDetailsException(
        status_code=HTTP_503_SERVICE_UNAVAILABLE,
        title="Service Unavailable",
        detail="Service temporarily unavailable",
        type_=f"{_TYPE_BASE}:service-unavailable",
    )


def _internal_500(exc: Exception, *, log_event: str) -> ProblemDetailsException:
    _log.error(log_event, error_type=type(exc).__name__, exc_info=exc)
    return ProblemDetailsException(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="Internal server error",
        type_=f"{_TYPE_BASE}:internal",
    )


def unexpected_to_problem(exc: Exception) -> ProblemDetailsException:
    # PROD-only catch-all; not registered in DEV (debug renderer shows traceback).
    return _internal_500(exc, log_event="unhandled exception")


def problem_handler(request: Request, exc: ProblemDetailsException) -> Response:
    # Converters can't see the request, so set RFC 9457 "instance" here.
    if exc.instance is None:
        exc.instance = request.url.path
    return exc.to_response(request)
