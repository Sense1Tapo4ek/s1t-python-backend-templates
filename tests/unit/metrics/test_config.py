from pathlib import Path

import pytest

from metrics.config import MetricsConfig


class TestMetricsConfigDefaults:
    def test_kept_fields_and_multiproc_dir_default(self) -> None:
        """
        Given no env overrides,
        When constructing MetricsConfig,
        Then kept fields (prom_endpoint_path, prom_endpoint_public, http_buckets)
        are present with defaults, and multiproc_dir defaults to
        <volume_path>/prometheus.
        """
        cfg = MetricsConfig()
        assert cfg.prom_endpoint_path == "/metrics"
        assert cfg.prom_endpoint_public is False
        assert len(cfg.http_buckets) >= 5
        assert all(b > 0 for b in cfg.http_buckets)

        # multiproc_dir must resolve to <volume_path>/prometheus
        assert cfg.multiproc_dir == cfg.volume_path / "prometheus"

    def test_removed_fields_absent(self) -> None:
        """
        Given MetricsConfig,
        When accessing removed fields,
        Then AttributeError is raised (fields gone).
        """
        cfg = MetricsConfig()
        with pytest.raises(AttributeError):
            _ = cfg.enabled
        with pytest.raises(AttributeError):
            _ = cfg.publish_interval_s
        with pytest.raises(AttributeError):
            _ = cfg.key_prefix
        with pytest.raises(AttributeError):
            _ = cfg.key_ttl_s
        with pytest.raises(AttributeError):
            _ = cfg.process_buckets

    def test_multiproc_dir_absolute_path(self) -> None:
        """
        Given MetricsConfig with default multiproc_dir,
        When accessing multiproc_dir,
        Then it is an absolute Path.
        """
        cfg = MetricsConfig()
        assert isinstance(cfg.multiproc_dir, Path)
        assert cfg.multiproc_dir.is_absolute()
