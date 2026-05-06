from admin.log.domain import LogEntryEnt


def _make(**overrides) -> LogEntryEnt:
    base = dict(
        id=1,
        timestamp="2026-04-29T12:00:00+00:00",
        level="INFO",
        logger="test",
        event="hello",
        pathname="/src/test.py",
        lineno=10,
        func_name="test_func",
        raw_json='{"event": "hello"}',
    )
    base.update(overrides)
    return LogEntryEnt(**base)


class TestLogEntryEntCore:
    def test_required_fields_round_trip(self) -> None:
        entry = _make()

        assert entry.id == 1
        assert entry.level == "INFO"
        assert entry.event == "hello"

    def test_trace_correlation_defaults_to_none(self) -> None:
        entry = _make()

        assert entry.trace_id is None
        assert entry.span_id is None

    def test_trace_correlation_round_trip(self) -> None:
        entry = _make(trace_id="t_abc123", span_id="s_xyz789")

        assert entry.trace_id == "t_abc123"
        assert entry.span_id == "s_xyz789"
