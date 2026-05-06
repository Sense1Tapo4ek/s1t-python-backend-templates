"""Flow tests for the schema → LogFilterVo translation: DSL parsing + explicit override."""

import json

import pytest

from admin.log.domain import DslSyntaxError, LogEntryEnt
from admin.log.domain.types import LogId
from admin.log.ports.driving.facades.logs_facade import (
    _build_filter_vo,
    _to_entry_schema,
)
from admin.log.ports.driving.schemas import LogFilterSchema


class TestFacadeDslParsing:
    def test_q_string_routed_through_dsl_parser(self) -> None:
        schema = LogFilterSchema(q="level:WARN+ logger:auth")

        vo = _build_filter_vo(schema)

        assert vo is not None
        assert vo.min_level == "WARN"
        assert vo.loggers == ("auth",)

    def test_explicit_min_level_overrides_dsl(self) -> None:
        schema = LogFilterSchema(q="level:WARN+", min_level="ERROR")

        vo = _build_filter_vo(schema)
        assert vo is not None

        assert vo.min_level == "ERROR"

    def test_live_mode_propagates(self) -> None:
        schema = LogFilterSchema(q="logger:auth", live_mode=True)

        vo = _build_filter_vo(schema)
        assert vo is not None

        assert vo.live_mode is True

    def test_invalid_dsl_raises_dsl_syntax_error(self) -> None:
        schema = LogFilterSchema(q="level:VERBOSE")

        with pytest.raises(DslSyntaxError):
            _build_filter_vo(schema)

    def test_empty_q_yields_empty_vo(self) -> None:
        schema = LogFilterSchema(q="")

        vo = _build_filter_vo(schema)

        assert vo is not None
        assert vo.min_level is None
        assert vo.fts_phrase is None

    def test_none_schema_returns_none(self) -> None:
        assert _build_filter_vo(None) is None

    def test_levels_propagates_as_tuple(self) -> None:
        schema = LogFilterSchema(levels=["INFO", "WARNING"])

        vo = _build_filter_vo(schema)

        assert vo is not None
        assert vo.levels == ("INFO", "WARNING")
        assert vo.min_level is None

    def test_levels_overrides_min_level_when_both_present(self) -> None:
        schema = LogFilterSchema(levels=["ERROR"], min_level="DEBUG")

        vo = _build_filter_vo(schema)
        assert vo is not None

        assert vo.levels == ("ERROR",)
        assert vo.min_level is None

    def test_min_level_used_when_levels_empty(self) -> None:
        schema = LogFilterSchema(levels=[], min_level="WARN")

        vo = _build_filter_vo(schema)
        assert vo is not None

        assert vo.levels is None
        assert vo.min_level == "WARN"


def _entry(raw: dict | str, **overrides) -> LogEntryEnt:
    raw_json = raw if isinstance(raw, str) else json.dumps(raw)
    base = dict(
        id=LogId(1),
        timestamp="2026-05-06T12:00:00Z",
        level="INFO",
        logger="ordering.app",
        event="order paid",
        pathname="/x.py",
        lineno=42,
        func_name="pay",
        raw_json=raw_json,
        trace_id=None,
        span_id=None,
    )
    base.update(overrides)
    return LogEntryEnt(**base)


class TestEntrySchemaMapping:
    """The wire schema strips promoted columns from raw_json into context_json
    so the SSE payload doesn't ship every value twice."""

    def test_promoted_keys_dropped_from_context_json(self) -> None:
        ent = _entry({
            "timestamp": "2026-05-06T12:00:00Z",
            "level": "INFO",
            "logger": "ordering.app",
            "event": "order paid",
            "pathname": "/x.py",
            "lineno": 42,
            "func_name": "pay",
            "user_id": 7,
            "amount": "99.50",
        })

        schema = _to_entry_schema(ent)

        ctx = json.loads(schema.context_json)
        assert ctx == {"user_id": 7, "amount": "99.50"}

    def test_promoted_columns_remain_at_top_level(self) -> None:
        ent = _entry({"event": "x", "user_id": 1})

        schema = _to_entry_schema(ent)

        assert schema.timestamp == "2026-05-06T12:00:00Z"
        assert schema.level == "INFO"
        assert schema.logger == "ordering.app"
        assert schema.event == "order paid"
        assert schema.id == 1

    def test_empty_context_serializes_as_empty_object(self) -> None:
        """Records with no extras must still produce valid JSON for client parse."""
        ent = _entry({
            "timestamp": "2026-05-06T12:00:00Z",
            "level": "INFO",
            "event": "ping",
        })

        schema = _to_entry_schema(ent)

        assert schema.context_json == "{}"

    def test_invalid_raw_json_yields_empty_context(self) -> None:
        """A corrupt record must not crash the response — degrades to empty."""
        ent = _entry("not-json-at-all")

        schema = _to_entry_schema(ent)

        assert schema.context_json == "{}"

    def test_non_dict_raw_json_yields_empty_context(self) -> None:
        """raw_json that decodes to a list/scalar is rejected silently."""
        ent = _entry("[1, 2, 3]")

        schema = _to_entry_schema(ent)

        assert schema.context_json == "{}"

    def test_context_json_uses_compact_separators(self) -> None:
        """Every byte counts on SSE — no whitespace in the JSON encoding."""
        ent = _entry({"event": "x", "a": 1, "b": 2})

        schema = _to_entry_schema(ent)

        assert " " not in schema.context_json
        assert ": " not in schema.context_json
