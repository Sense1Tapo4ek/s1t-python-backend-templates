from typing import ClassVar

from prometheus_client import Counter, Gauge, Histogram


class PrometheusSink:
    """Generic by-name Prometheus sink (implements IMetricsSink).

    Metric objects are cached at class level so repeated construction (app
    reloads, multiple create_app() calls in tests) reuses the same series and
    never trips prometheus_client's duplicate-registration guard. The three
    ``widget_*`` metrics are deletable demo examples.

    A metric name's label set is fixed at first use (prometheus enforces one
    label set per name); calling the same name with a different set of label
    keys is a programming error and raises.
    """

    _counters: ClassVar[dict[str, Counter]] = {}
    _gauges: ClassVar[dict[str, Gauge]] = {}
    _histograms: ClassVar[dict[str, Histogram]] = {}

    def __init__(self) -> None:
        self._counter("widget_render_total", (), "Demo widgets rendered.")
        self._gauge("widget_queue_depth", (), "Demo widgets currently queued.")
        self._histogram("widget_render_seconds", (), "Demo widget render duration (seconds).")

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        metric = self._counter(name, tuple(sorted(labels)))
        (metric.labels(**labels) if labels else metric).inc(value)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        metric = self._gauge(name, tuple(sorted(labels)))
        (metric.labels(**labels) if labels else metric).set(value)

    def observe(self, name: str, value: float, **labels: str) -> None:
        metric = self._histogram(name, tuple(sorted(labels)))
        (metric.labels(**labels) if labels else metric).observe(value)

    def _counter(self, name: str, labelnames: tuple[str, ...], doc: str | None = None) -> Counter:
        metric = self._counters.get(name)
        if metric is None:
            metric = Counter(name, doc or f"Counter {name}.", labelnames=labelnames)
            self._counters[name] = metric
        return metric

    def _gauge(self, name: str, labelnames: tuple[str, ...], doc: str | None = None) -> Gauge:
        metric = self._gauges.get(name)
        if metric is None:
            # livesum: sum the per-process values on scrape under multiprocess mode.
            metric = Gauge(name, doc or f"Gauge {name}.", labelnames=labelnames,
                           multiprocess_mode="livesum")
            self._gauges[name] = metric
        return metric

    def _histogram(
        self, name: str, labelnames: tuple[str, ...], doc: str | None = None
    ) -> Histogram:
        metric = self._histograms.get(name)
        if metric is None:
            metric = Histogram(name, doc or f"Histogram {name}.", labelnames=labelnames)
            self._histograms[name] = metric
        return metric
