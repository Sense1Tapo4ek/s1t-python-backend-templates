from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from admin.log.domain import InvalidLogFilterError, LogFilterVo


class TestLogFilterVoDefaults:
    def test_empty_factory_returns_all_none(self) -> None:
        f = LogFilterVo.empty()

        assert f.min_level is None
        assert f.levels is None
        assert f.loggers is None
        assert f.trace_id is None
        assert f.kv_filters is None
        assert f.time_from is None
        assert f.time_to is None
        assert f.fts_phrase is None
        assert f.live_mode is False

    def test_default_constructor_matches_empty(self) -> None:
        assert LogFilterVo() == LogFilterVo.empty()


class TestLogFilterVoConstruction:
    def test_accepts_full_filter(self) -> None:
        f = LogFilterVo(
            levels=("ERROR", "CRITICAL"),
            loggers=("ordering.*", "auth"),
            trace_id="abc123",
            kv_filters=(("user_id", "42"),),
            time_from=datetime(2026, 1, 1, tzinfo=UTC),
            time_to=datetime(2026, 12, 31, tzinfo=UTC),
            fts_phrase="payment failed",
            live_mode=True,
        )

        assert f.levels == ("ERROR", "CRITICAL")
        assert f.loggers == ("ordering.*", "auth")
        assert f.trace_id == "abc123"
        assert f.kv_filters == (("user_id", "42"),)
        assert f.time_from.year == 2026
        assert f.fts_phrase == "payment failed"
        assert f.live_mode is True

    def test_min_level_and_levels_mutually_exclusive(self) -> None:
        with pytest.raises(InvalidLogFilterError) as exc:
            LogFilterVo(min_level="WARN", levels=("ERROR",))
        assert exc.value.field == "levels"

    def test_empty_levels_tuple_rejected(self) -> None:
        with pytest.raises(InvalidLogFilterError) as exc:
            LogFilterVo(levels=())
        assert exc.value.field == "levels"


class TestLogFilterVoImmutability:
    def test_is_frozen(self) -> None:
        f = LogFilterVo()

        with pytest.raises(Exception) as exc:
            f.min_level = "ERROR"
        assert "frozen" in str(exc.value).lower() or "FrozenInstanceError" in type(exc.value).__name__

    def test_equality_by_value(self) -> None:
        a = LogFilterVo(min_level="WARN", trace_id="xyz")
        b = LogFilterVo(min_level="WARN", trace_id="xyz")
        assert a == b


class TestLogFilterVoValidation:
    def test_valid_min_level_succeeds(self) -> None:
        f = LogFilterVo(min_level="WARN")
        assert f.min_level == "WARN"

    def test_unknown_min_level_rejected(self) -> None:
        with pytest.raises(InvalidLogFilterError) as exc:
            LogFilterVo(min_level="bogus")
        assert exc.value.field == "min_level"

    def test_unknown_level_in_levels_rejected(self) -> None:
        with pytest.raises(InvalidLogFilterError) as exc:
            LogFilterVo(levels=("WARN", "BAD"))
        assert exc.value.field == "levels"

    def test_empty_glob_logger_rejected(self) -> None:
        with pytest.raises(InvalidLogFilterError) as exc:
            LogFilterVo(loggers=(".*",))
        assert exc.value.field == "loggers"

    def test_non_empty_glob_prefix_succeeds(self) -> None:
        f = LogFilterVo(loggers=("admin.*",))
        assert f.loggers == ("admin.*",)

    def test_invalid_kv_key_rejected(self) -> None:
        with pytest.raises(InvalidLogFilterError) as exc:
            LogFilterVo(kv_filters=(("bad key", "v"),))
        assert exc.value.field == "kv_filters"

    def test_empty_filter_succeeds(self) -> None:
        assert LogFilterVo() is not None

    def test_inverted_time_range_rejected(self) -> None:
        """
        Given time_from later than time_to,
        When constructing the VO,
        Then InvalidLogFilterError is raised with field='time_to'.
        """
        now = datetime.now(UTC)
        with pytest.raises(InvalidLogFilterError) as exc:
            LogFilterVo(time_from=now, time_to=now - timedelta(hours=1))
        assert exc.value.field == "time_to"

    def test_equal_time_range_succeeds(self) -> None:
        """
        Given time_from == time_to (single instant),
        When constructing the VO,
        Then no error is raised.
        """
        now = datetime.now(UTC)
        assert LogFilterVo(time_from=now, time_to=now) is not None

    def test_replace_re_runs_validation(self) -> None:
        """
        Given a valid VO,
        When dataclasses.replace overrides a field with an invalid value,
        Then InvalidLogFilterError fires (proves __post_init__ runs on replace).
        """
        base = LogFilterVo(min_level="WARN")
        with pytest.raises(InvalidLogFilterError) as exc:
            replace(base, min_level="bogus")
        assert exc.value.field == "min_level"
