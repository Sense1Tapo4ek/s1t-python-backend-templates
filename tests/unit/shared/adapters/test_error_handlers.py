"""Generic layer-error handlers — verify status codes and that internal
detail (str(exc)) never leaks to the response body."""

from unittest.mock import MagicMock

from litestar.status_codes import (
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from shared.adapters.error_handlers import (
    adapter_error_handler,
    app_error_handler,
    domain_error_handler,
    port_error_handler,
)
from shared.generics.errors import AdapterError, AppError, DomainError, PortError

_INTERNAL_DETAIL = "secret SQL fragment: SELECT * FROM users WHERE id=42"


def _request() -> MagicMock:
    return MagicMock()


class TestDomainErrorHandler:
    def test_returns_409_with_generic_detail(self) -> None:
        response = domain_error_handler(_request(), DomainError(_INTERNAL_DETAIL))

        assert response.status_code == HTTP_409_CONFLICT
        assert response.content == {"detail": "Conflict"}
        assert _INTERNAL_DETAIL not in str(response.content)


class TestAppErrorHandler:
    def test_returns_422_with_generic_detail(self) -> None:
        response = app_error_handler(_request(), AppError(_INTERNAL_DETAIL))

        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        assert response.content == {"detail": "Unprocessable"}
        assert _INTERNAL_DETAIL not in str(response.content)


class TestPortErrorHandler:
    def test_returns_503_and_hides_internal_detail(self) -> None:
        response = port_error_handler(_request(), PortError(_INTERNAL_DETAIL))

        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert response.content == {"detail": "Service unavailable"}
        assert _INTERNAL_DETAIL not in str(response.content)


class TestAdapterErrorHandler:
    def test_returns_500_and_hides_internal_detail(self) -> None:
        response = adapter_error_handler(_request(), AdapterError(_INTERNAL_DETAIL))

        assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
        assert response.content == {"detail": "Internal server error"}
        assert _INTERNAL_DETAIL not in str(response.content)
