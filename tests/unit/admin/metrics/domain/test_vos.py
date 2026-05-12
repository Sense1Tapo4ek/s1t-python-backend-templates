import pytest

from admin.metrics.domain import (
    MetricKvVo,
    ModuleDetailVo,
    ModuleSummaryVo,
    Severity,
)


class TestMetricKvVo:
    def test_frozen(self) -> None:
        kv = MetricKvVo(label="x", value="1", severity=Severity.OK)
        with pytest.raises(AttributeError):
            kv.label = "y"  # type: ignore[misc]


class TestModuleSummaryVo:
    def test_at_least_one_kv_required(self) -> None:
        with pytest.raises(ValueError):
            ModuleSummaryVo(slug="x", name="X", kvs=())


class TestModuleDetailVo:
    def test_sections_can_be_empty(self) -> None:
        d = ModuleDetailVo(slug="x", name="X", sections=())
        assert d.slug == "x"
