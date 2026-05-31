from admin.log.ports.errors import LogReadError
from shared.generics.errors import PortError


class TestLogReadError:
    def test_is_port_error(self) -> None:
        """
        Given LogReadError,
        When inspected,
        Then it is a PortError subclass.
        """
        assert issubclass(LogReadError, PortError)

    def test_wraps_path_and_reason(self) -> None:
        """
        Given a file path and a reason,
        When the error is constructed,
        Then both are stored and the message is human-readable.
        """
        err = LogReadError(path="/data/app.jsonl", reason="No such file")

        assert err.path == "/data/app.jsonl"
        assert err.reason == "No such file"
        assert "/data/app.jsonl" in str(err)
