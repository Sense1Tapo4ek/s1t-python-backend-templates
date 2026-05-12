import pytest

from admin.metrics.domain import Severity, classify


class TestSeverityClassify:
    def test_below_warn_is_ok(self) -> None:
        """Given thresholds (warn=200, bad=500), 100 -> OK."""
        assert classify(100, warn=200, bad=500) is Severity.OK

    def test_between_warn_and_bad_is_warn(self) -> None:
        assert classify(300, warn=200, bad=500) is Severity.WARN

    def test_at_or_above_bad_is_bad(self) -> None:
        assert classify(500, warn=200, bad=500) is Severity.BAD
        assert classify(1000, warn=200, bad=500) is Severity.BAD

    def test_inverted_thresholds_rejected(self) -> None:
        """Given warn > bad (impossible), classify raises ValueError."""
        with pytest.raises(ValueError):
            classify(100, warn=600, bad=500)

    def test_zero_only_alarm(self) -> None:
        """When warn=None and bad>0, only zero is OK; rest is BAD."""
        assert classify(0, warn=None, bad=1) is Severity.OK
        assert classify(1, warn=None, bad=1) is Severity.BAD
