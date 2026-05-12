import pytest

from admin.metrics.config import MetricsConfig


class TestMetricsConfigDefaults:
    def test_defaults_are_safe_by_default(self) -> None:
        """
        Given no env overrides,
        When constructing MetricsConfig,
        Then enabled is true (UI on), prom endpoint is admin-guarded,
        publish interval is 5s and TTL is 30s.
        """
        cfg = MetricsConfig()
        assert cfg.enabled is True
        assert cfg.prom_endpoint_public is False
        assert cfg.prom_endpoint_path == "/metrics"
        assert cfg.publish_interval_s == 5.0
        assert cfg.key_ttl_s == 30
        assert cfg.key_prefix == "metrics:"
        assert len(cfg.http_buckets) >= 5
        assert all(b > 0 for b in cfg.http_buckets)


class TestMetricsConfigValidation:
    def test_publish_interval_below_one_rejected(self, monkeypatch) -> None:
        """
        Given METRICS_PUBLISH_INTERVAL_S below 1.0,
        When constructing MetricsConfig,
        Then a validation error is raised — short interval risks
        exceeding the TTL window and orphaning live workers.
        """
        monkeypatch.setenv("METRICS_PUBLISH_INTERVAL_S", "0.5")
        with pytest.raises(ValueError):
            MetricsConfig()

    def test_ttl_below_five_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("METRICS_KEY_TTL_S", "1")
        with pytest.raises(ValueError):
            MetricsConfig()
