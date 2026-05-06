"""Specialised admin/log handlers — must surface structured detail
(position/reason, field/reason) so the UI can highlight the offending
input. These bypass the generic DomainError handler that masks detail."""

from unittest.mock import MagicMock

from litestar.status_codes import HTTP_400_BAD_REQUEST

from admin.log.adapters.driving.error_handlers import (
    dsl_syntax_handler,
    invalid_log_filter_handler,
)
from admin.log.domain import DslSyntaxError, InvalidLogFilterError


def _request() -> MagicMock:
    return MagicMock()


class TestDslSyntaxHandler:
    def test_surfaces_position_and_reason(self) -> None:
        """
        Given a DslSyntaxError with position+reason,
        When the handler runs,
        Then 400 with body shaped {position, reason} for UI caret rendering.
        """
        exc = DslSyntaxError(position=12, reason="unclosed quote")

        response = dsl_syntax_handler(_request(), exc)

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.content == {"position": 12, "reason": "unclosed quote"}


class TestInvalidLogFilterHandler:
    def test_surfaces_field_and_reason(self) -> None:
        """
        Given an InvalidLogFilterError,
        When the handler runs,
        Then 400 with body shaped {field, reason} so the form can highlight
        the offending input. Specialised handler bypasses the generic
        DomainError mapper that would mask detail.
        """
        exc = InvalidLogFilterError(field="kv_filters", reason="empty key")

        response = invalid_log_filter_handler(_request(), exc)

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.content == {"field": "kv_filters", "reason": "empty key"}
