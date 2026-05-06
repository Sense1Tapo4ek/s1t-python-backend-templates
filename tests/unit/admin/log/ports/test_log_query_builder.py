from datetime import UTC, datetime

import pytest

from admin.log.domain import InvalidLogFilterError, LogFilterVo
from admin.log.ports.driven.repos.log_query_builder import build_select


class TestEmptyAndDefault:
    def test_no_filter_yields_select_all_desc(self) -> None:
        q = build_select(None)
        assert q.sql == "SELECT * FROM logs ORDER BY id DESC"
        assert q.params == ()

    def test_empty_filter_same_as_none(self) -> None:
        q = build_select(LogFilterVo.empty())
        assert "ORDER BY id DESC" in q.sql
        assert q.params == ()


class TestPagination:
    def test_limit_appended_as_placeholder(self) -> None:
        q = build_select(None, limit=50)
        assert q.sql.endswith("LIMIT ?")
        assert q.params[-1] == 50

    def test_limit_zero_emits_clause(self) -> None:
        q = build_select(None, limit=0)
        assert q.sql.endswith("LIMIT ?")
        assert q.params[-1] == 0

    def test_negative_limit_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_select(None, limit=-1)

    def test_before_cursor_adds_id_predicate(self) -> None:
        q = build_select(None, limit=50, before_cursor=999)
        assert "id < ?" in q.sql
        assert 999 in q.params

    def test_after_cursor_adds_id_predicate(self) -> None:
        q = build_select(None, limit=50, after_cursor=10)
        assert "id > ?" in q.sql
        assert 10 in q.params

    def test_order_asc(self) -> None:
        q = build_select(None, order="ASC")
        assert "ORDER BY id ASC" in q.sql

    def test_invalid_order_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_select(None, order="DROP")


class TestMinLevel:
    def test_min_level_uses_rank_case(self) -> None:
        q = build_select(LogFilterVo(min_level="WARN"))
        assert "CASE level" in q.sql
        assert ">= ?" in q.sql
        assert 30 in q.params

    def test_unknown_min_level_rejected_at_vo(self) -> None:
        with pytest.raises(InvalidLogFilterError):
            build_select(LogFilterVo(min_level="VERBOSE"))


class TestExactLevels:
    def test_levels_in_clause(self) -> None:
        q = build_select(LogFilterVo(levels=("ERROR", "CRITICAL")))
        assert "level IN (?, ?)" in q.sql
        assert q.params == ("ERROR", "CRITICAL")

    def test_levels_normalized_to_upper(self) -> None:
        q = build_select(LogFilterVo(levels=("warn",)))
        assert q.params == ("WARN",)


class TestLoggers:
    def test_exact_logger(self) -> None:
        q = build_select(LogFilterVo(loggers=("auth",)))
        assert "logger = ?" in q.sql
        assert "auth" in q.params

    def test_glob_logger_uses_like(self) -> None:
        q = build_select(LogFilterVo(loggers=("ordering.*",)))
        assert "logger LIKE ? || '.%'" in q.sql
        assert "ordering" in q.params

    def test_multiple_loggers_or_joined(self) -> None:
        q = build_select(LogFilterVo(loggers=("auth", "ordering.*")))
        assert " OR " in q.sql
        # both patterns in params
        assert "auth" in q.params
        assert "ordering" in q.params

    def test_empty_glob_prefix_rejected_at_vo(self) -> None:
        with pytest.raises(InvalidLogFilterError, match="non-empty prefix"):
            build_select(LogFilterVo(loggers=(".*",)))


class TestTraceId:
    def test_trace_id_predicate(self) -> None:
        q = build_select(LogFilterVo(trace_id="abc1234567890def"))
        assert "trace_id = ?" in q.sql
        assert "abc1234567890def" in q.params


class TestKvFilters:
    def test_simple_kv(self) -> None:
        q = build_select(LogFilterVo(kv_filters=(("user_id", "42"),)))
        assert "json_extract(raw_json, ?) = ?" in q.sql
        assert "$.user_id" in q.params
        assert "42" in q.params

    def test_dotted_key_allowed(self) -> None:
        q = build_select(LogFilterVo(kv_filters=(("ctx.user.id", "x"),)))
        assert "$.ctx.user.id" in q.params

    def test_multiple_kv_and_joined(self) -> None:
        q = build_select(
            LogFilterVo(kv_filters=(("user_id", "1"), ("order_id", "2")))
        )
        assert q.sql.count("json_extract") == 2

    @pytest.mark.parametrize("malicious_key", [
        "user_id; DROP TABLE logs",
        "x' OR '1'='1",
        "weird-key",
        "café",
    ])
    def test_malicious_kv_key_rejected_at_vo(self, malicious_key: str) -> None:
        with pytest.raises(InvalidLogFilterError, match="invalid kv key"):
            build_select(LogFilterVo(kv_filters=((malicious_key, "x"),)))


class TestKvBindingDefenseInDepth:
    def test_kv_path_bound_as_parameter_not_interpolated(self) -> None:
        q = build_select(LogFilterVo(kv_filters=(("user_id", "42"),)))
        # SQL contains placeholders only — no literal key in the SQL string.
        assert "user_id" not in q.sql
        assert "$." not in q.sql
        # The path is in params instead.
        assert "$.user_id" in q.params

    def test_injection_attempt_in_kv_key_rejected_by_vo(self) -> None:
        with pytest.raises(InvalidLogFilterError, match="invalid kv key"):
            build_select(
                LogFilterVo(kv_filters=(("x', 1) OR ('1", "v"),))
            )


class TestFts5Sanitization:
    def test_plain_text_wrapped_as_phrase(self) -> None:
        q = build_select(LogFilterVo(fts_phrase="order paid"))
        assert '"order paid"' in q.params

    def test_fts5_operators_neutralized_as_literal_phrase(self) -> None:
        q = build_select(LogFilterVo(fts_phrase="event:* OR level:*"))
        assert '"event:* OR level:*"' in q.params
        # The raw unescaped string must not appear in params.
        assert "event:* OR level:*" not in [
            p for p in q.params if p != '"event:* OR level:*"'
        ]

    def test_embedded_quotes_doubled(self) -> None:
        q = build_select(LogFilterVo(fts_phrase='she said "hi"'))
        assert '"she said ""hi"""' in q.params


class TestTimeRange:
    def test_time_from_iso(self) -> None:
        q = build_select(
            LogFilterVo(time_from=datetime(2026, 1, 1, tzinfo=UTC))
        )
        assert "timestamp >= ?" in q.sql
        assert "2026-01-01T00:00:00+00:00" in q.params

    def test_time_to_iso(self) -> None:
        q = build_select(
            LogFilterVo(time_to=datetime(2026, 12, 31, tzinfo=UTC))
        )
        assert "timestamp <= ?" in q.sql

    def test_time_range_both_bounds(self) -> None:
        q = build_select(
            LogFilterVo(
                time_from=datetime(2026, 1, 1, tzinfo=UTC),
                time_to=datetime(2026, 6, 1, tzinfo=UTC),
            )
        )
        assert "timestamp >= ?" in q.sql
        assert "timestamp <= ?" in q.sql


class TestTextSearch:
    def test_text_search_uses_fts_join(self) -> None:
        q = build_select(LogFilterVo(fts_phrase="payment failed"))
        assert "JOIN logs_fts" in q.sql
        assert "logs_fts MATCH ?" in q.sql
        assert '"payment failed"' in q.params

    def test_no_text_search_no_fts_join(self) -> None:
        q = build_select(LogFilterVo(min_level="WARN"))
        assert "logs_fts" not in q.sql


class TestCombined:
    def test_full_filter_composes_correctly(self) -> None:
        f = LogFilterVo(
            min_level="WARN",
            loggers=("ordering.*",),
            trace_id="abc1234567890def",
            kv_filters=(("user_id", "42"),),
            time_from=datetime(2026, 1, 1, tzinfo=UTC),
            fts_phrase="failed",
        )
        q = build_select(f, limit=100, before_cursor=500)
        assert "JOIN logs_fts" in q.sql
        assert "CASE level" in q.sql
        assert "logger LIKE" in q.sql
        assert "trace_id = ?" in q.sql
        assert "json_extract(raw_json, ?) = ?" in q.sql
        assert "timestamp >= ?" in q.sql
        assert "logs_fts MATCH ?" in q.sql
        assert "id < ?" in q.sql
        assert "LIMIT ?" in q.sql
        assert q.params[-1] == 100
