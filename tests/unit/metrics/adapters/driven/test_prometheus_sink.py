from prometheus_client import REGISTRY

from metrics.adapters.driven import PrometheusSink


class TestPrometheusSink:
    def test_demo_metrics_predeclared(self) -> None:
        """
        Given a fresh PrometheusSink,
        When constructed,
        Then the three demo metrics are registered under their right types.
        """
        PrometheusSink()
        assert "widget_render_total" in PrometheusSink._counters
        assert "widget_queue_depth" in PrometheusSink._gauges
        assert "widget_render_seconds" in PrometheusSink._histograms

    def test_increment_adds_to_counter_value(self) -> None:
        """Given a sink, When increment() twice, Then the counter total is 2."""
        sink = PrometheusSink()
        sink.increment("unit_val_counter_total")
        sink.increment("unit_val_counter_total")
        assert REGISTRY.get_sample_value("unit_val_counter_total") == 2.0

    def test_set_gauge_sets_value(self) -> None:
        """Given a sink, When set_gauge(), Then the gauge reads that value."""
        sink = PrometheusSink()
        sink.set_gauge("unit_val_gauge", 7)
        assert REGISTRY.get_sample_value("unit_val_gauge") == 7.0

    def test_observe_records_into_histogram(self) -> None:
        """Given a sink, When observe() once, Then the histogram count is 1."""
        sink = PrometheusSink()
        sink.observe("unit_val_hist_seconds", 0.01)
        assert REGISTRY.get_sample_value("unit_val_hist_seconds_count") == 1.0

    def test_second_instance_reuses_cached_metric(self) -> None:
        """
        Given one sink instance,
        When a second is constructed,
        Then the demo counter object is the SAME (class-level cache, no
        duplicate-registration error).
        """
        PrometheusSink()
        first = PrometheusSink._counters["widget_render_total"]
        PrometheusSink()
        assert PrometheusSink._counters["widget_render_total"] is first
