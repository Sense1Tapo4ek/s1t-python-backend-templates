import pytest

from admin.log.ports.driving.schemas import LogEntrySchema, LogPageResponseSchema


class TestLogPageResponseSchema:
    def test_page_holds_entries_and_optional_cursor(self) -> None:
        """
        Given a list of entries and an opaque cursor string,
        When building LogPageResponseSchema,
        Then entries and cursor round-trip and cursor may be None.
        """
        # Arrange
        entry = LogEntrySchema(
            timestamp="2026-06-01T00:00:00Z",
            level="INFO",
            logger="root",
            event="hello",
            context_json="{}",
        )

        # Act
        page = LogPageResponseSchema(entries=[entry], cursor="aW5vZGU6MA==")

        # Assert
        assert page.entries[0].event == "hello"
        assert page.cursor == "aW5vZGU6MA=="
        assert LogPageResponseSchema(entries=[]).cursor is None

    def test_dsl_and_clear_schemas_are_gone(self) -> None:
        """
        Given the simplified module,
        When importing removed names,
        Then ImportError is raised.
        """
        # Act / Assert
        with pytest.raises(ImportError):
            from admin.log.ports.driving.schemas import (  # noqa: F401
                ClearLogsResponseSchema,
            )
        with pytest.raises(ImportError):
            from admin.log.ports.driving.schemas import LogFilterSchema  # noqa: F401
