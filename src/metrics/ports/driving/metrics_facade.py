from dataclasses import dataclass

from ...app import IMetricsSink


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricsFacade:
    _sink: IMetricsSink

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        self._sink.increment(name, value, **labels)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        self._sink.set_gauge(name, value, **labels)

    def observe(self, name: str, value: float, **labels: str) -> None:
        self._sink.observe(name, value, **labels)
