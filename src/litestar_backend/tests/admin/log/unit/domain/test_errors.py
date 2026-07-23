from admin.log.domain import MalformedLogLine
from shared.generics.errors import DomainError


class TestMalformedLogLine:
    def test_is_domain_error(self) -> None:
        """
        Given MalformedLogLine,
        When inspected,
        Then it is a DomainError subclass.
        """
        assert issubclass(MalformedLogLine, DomainError)

    def test_carries_preview(self) -> None:
        """
        Given a malformed line preview,
        When the error is constructed,
        Then the preview is stored and rendered in the message.
        """
        err = MalformedLogLine(preview="garbage{")

        assert err.preview == "garbage{"
        assert "garbage{" in str(err)
