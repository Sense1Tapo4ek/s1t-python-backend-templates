from datetime import UTC, datetime

import pytest

from admin.log.domain import DslParser, DslSyntaxError


class TestEmptyAndBareInput:
    def test_empty_string_returns_empty_filter(self) -> None:
        f = DslParser.parse("")
        assert f.fts_phrase is None
        assert f.min_level is None

    def test_whitespace_only_returns_empty_filter(self) -> None:
        f = DslParser.parse("   \t  ")
        assert f.fts_phrase is None

    def test_bare_words_become_text_search(self) -> None:
        f = DslParser.parse("payment failed")
        assert f.fts_phrase == "payment failed"


class TestLevelToken:
    def test_min_level_with_plus_suffix(self) -> None:
        f = DslParser.parse("level:WARN+")
        assert f.min_level == "WARN"
        assert f.levels is None

    def test_exact_level_accumulates_into_levels(self) -> None:
        f = DslParser.parse("level:ERROR level:CRITICAL")
        assert f.levels == ("ERROR", "CRITICAL")
        assert f.min_level is None

    def test_level_value_normalized_to_upper(self) -> None:
        f = DslParser.parse("level:warn")
        assert f.levels == ("WARN",)

    def test_unknown_level_raises_with_position(self) -> None:
        with pytest.raises(DslSyntaxError) as exc_info:
            DslParser.parse("level:VERBOSE")
        assert exc_info.value.reason.startswith("unknown log level")
        assert exc_info.value.position == 0


class TestLoggerToken:
    def test_exact_logger(self) -> None:
        f = DslParser.parse("logger:auth")
        assert f.loggers == ("auth",)

    def test_glob_logger_kept_as_is(self) -> None:
        f = DslParser.parse("logger:ordering.*")
        assert f.loggers == ("ordering.*",)

    def test_multiple_loggers_accumulate(self) -> None:
        f = DslParser.parse("logger:auth logger:billing")
        assert f.loggers == ("auth", "billing")

    def test_empty_logger_value_raises(self) -> None:
        with pytest.raises(DslSyntaxError) as exc:
            DslParser.parse("logger:")
        assert "empty" in exc.value.reason


class TestTraceToken:
    def test_trace_id_extracted(self) -> None:
        f = DslParser.parse("trace:9c44b1a4f0123456")
        assert f.trace_id == "9c44b1a4f0123456"

    def test_empty_trace_value_raises(self) -> None:
        with pytest.raises(DslSyntaxError):
            DslParser.parse("trace:")

    @pytest.mark.parametrize("bad", [
        "trace:short",
        "trace:NOTHEX0000000000",
        "trace:9c44b1a4f01234567",  # 17 chars
        "trace:ABCDEF0123456789",   # uppercase
    ])
    def test_invalid_trace_format_raises(self, bad: str) -> None:
        with pytest.raises(DslSyntaxError) as exc:
            DslParser.parse(bad)
        assert "16 lowercase hex" in exc.value.reason


class TestLevelTokenConflicts:
    def test_min_level_then_exact_level_raises(self) -> None:
        with pytest.raises(DslSyntaxError) as exc:
            DslParser.parse("level:WARN+ level:ERROR")
        assert "mix" in exc.value.reason

    def test_exact_level_then_min_level_raises(self) -> None:
        with pytest.raises(DslSyntaxError) as exc:
            DslParser.parse("level:ERROR level:WARN+")
        assert "mix" in exc.value.reason

    def test_two_min_levels_raises(self) -> None:
        with pytest.raises(DslSyntaxError):
            DslParser.parse("level:WARN+ level:ERROR+")


class TestTimeRangeTokens:
    def test_from_iso_parsed(self) -> None:
        f = DslParser.parse("from:2026-01-01T00:00:00+00:00")
        assert f.time_from == datetime(2026, 1, 1, tzinfo=UTC)

    def test_from_with_z_suffix_normalized(self) -> None:
        f = DslParser.parse("from:2026-01-01T00:00:00Z")
        assert f.time_from == datetime(2026, 1, 1, tzinfo=UTC)

    def test_to_iso_parsed(self) -> None:
        f = DslParser.parse("to:2026-12-31T23:59:59Z")
        assert f.time_to.year == 2026

    def test_invalid_iso_raises_with_field_name(self) -> None:
        with pytest.raises(DslSyntaxError) as exc:
            DslParser.parse("from:not-a-date")
        assert "from" in exc.value.reason

    def test_empty_from_value_raises(self) -> None:
        with pytest.raises(DslSyntaxError):
            DslParser.parse("from:")


class TestKvTokens:
    def test_simple_kv(self) -> None:
        f = DslParser.parse("kv.user_id=42")
        assert f.kv_filters == (("user_id", "42"),)

    def test_quoted_kv_value(self) -> None:
        f = DslParser.parse('kv.path="/api/users"')
        assert f.kv_filters == (("path", "/api/users"),)

    def test_quoted_value_with_spaces(self) -> None:
        f = DslParser.parse('kv.message="payment failed for user"')
        assert f.kv_filters == (("message", "payment failed for user"),)

    def test_dotted_key_allowed(self) -> None:
        f = DslParser.parse("kv.context.user.id=42")
        assert f.kv_filters == (("context.user.id", "42"),)

    def test_multiple_kv_pairs_accumulate(self) -> None:
        f = DslParser.parse("kv.user_id=42 kv.order_id=8f3a")
        assert f.kv_filters == (("user_id", "42"), ("order_id", "8f3a"))

    def test_kv_without_equals_raises(self) -> None:
        with pytest.raises(DslSyntaxError) as exc:
            DslParser.parse("kv.user_id")
        assert "kv.<key>=<value>" in exc.value.reason

    def test_kv_empty_key_raises(self) -> None:
        with pytest.raises(DslSyntaxError):
            DslParser.parse("kv.=42")

    @pytest.mark.parametrize("malicious", [
        "kv.user_id;DROP=1",
        "kv.foo')--=1",
        "kv.café=1",
        "kv.weird-name=1",
    ])
    def test_kv_invalid_key_raises(self, malicious: str) -> None:
        """SQL-injection guard: keys not matching ^[a-zA-Z0-9_.]+$ are rejected."""
        with pytest.raises(DslSyntaxError) as exc:
            DslParser.parse(malicious)
        assert "invalid characters" in exc.value.reason


class TestMixedTokens:
    def test_full_query(self) -> None:
        """Plan example: every dimension at once."""
        f = DslParser.parse(
            'level:WARN+ logger:ordering.* trace:abc123def4567890 '
            'kv.user_id=42 from:2026-01-01T00:00:00Z payment failed'
        )

        assert f.min_level == "WARN"
        assert f.loggers == ("ordering.*",)
        assert f.trace_id == "abc123def4567890"
        assert f.kv_filters == (("user_id", "42"),)
        assert f.time_from == datetime(2026, 1, 1, tzinfo=UTC)
        assert f.fts_phrase == "payment failed"

    def test_unrecognized_colon_token_falls_through_to_text(self) -> None:
        """
        Given a token like 'foo:bar' that isn't a known DSL key,
        When parsed,
        Then it lands in fts_phrase rather than raising.
        """
        f = DslParser.parse("foo:bar baseline")
        assert f.fts_phrase == "foo:bar baseline"
