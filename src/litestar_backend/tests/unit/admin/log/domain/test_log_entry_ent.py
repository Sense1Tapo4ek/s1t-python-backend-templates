import pytest

from admin.log.domain import LogEntryEnt, MalformedLogLine


class TestLogEntryParse:
    def test_parse_valid_json_line(self) -> None:
        """
        Given a valid JSON log line,
        When parsed,
        Then promoted fields and raw dict are populated.
        """
        line = (
            '{"timestamp": "2026-05-31T10:00:00Z", "level": "INFO", '
            '"logger": "app", "event": "started", "extra": 1}'
        )

        ent = LogEntryEnt.parse(line)

        assert ent.timestamp == "2026-05-31T10:00:00Z"
        assert ent.level == "INFO"
        assert ent.logger == "app"
        assert ent.event == "started"
        assert ent.raw == {
            "timestamp": "2026-05-31T10:00:00Z",
            "level": "INFO",
            "logger": "app",
            "event": "started",
            "extra": 1,
        }

    def test_parse_tolerates_trailing_cr(self) -> None:
        """
        Given a CRLF-terminated line (CR not yet stripped by caller),
        When parsed,
        Then the trailing CR is ignored.
        """
        line = '{"timestamp": "t", "level": "INFO", "logger": "a", "event": "e"}\r'

        ent = LogEntryEnt.parse(line)

        assert ent.event == "e"

    def test_parse_missing_keys_uses_safe_defaults(self) -> None:
        """
        Given a JSON object missing promoted keys,
        When parsed,
        Then defaults fill the promoted fields and raw keeps the original.
        """
        ent = LogEntryEnt.parse('{"event": "only-event"}')

        assert ent.event == "only-event"
        assert ent.level == "INFO"
        assert ent.logger == ""
        assert ent.timestamp == ""
        assert ent.raw == {"event": "only-event"}

    def test_parse_non_json_raises(self) -> None:
        """
        Given a non-JSON line,
        When parsed,
        Then MalformedLogLine is raised.
        """
        with pytest.raises(MalformedLogLine):
            LogEntryEnt.parse("not json at all")

    def test_parse_non_object_json_raises(self) -> None:
        """
        Given valid JSON that is not an object (e.g. an array),
        When parsed,
        Then MalformedLogLine is raised.
        """
        with pytest.raises(MalformedLogLine):
            LogEntryEnt.parse("[1, 2, 3]")

    def test_parse_empty_line_raises(self) -> None:
        """
        Given an empty line,
        When parsed,
        Then MalformedLogLine is raised.
        """
        with pytest.raises(MalformedLogLine):
            LogEntryEnt.parse("")
