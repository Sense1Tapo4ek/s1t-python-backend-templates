from metrics.app import IMetricsSink
from metrics.ports.driving import MetricsFacade


class FakeSink(IMetricsSink):
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        self.calls.append(("inc", name, value, labels))

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        self.calls.append(("gauge", name, value, labels))

    def observe(self, name: str, value: float, **labels: str) -> None:
        self.calls.append(("obs", name, value, labels))


def test_facade_delegates_to_sink() -> None:
    """
    Given a MetricsFacade over a fake sink,
    When increment/set_gauge/observe are called (including labels),
    Then each delegates to the sink with the same args and labels.
    """
    sink = FakeSink()
    facade = MetricsFacade(_sink=sink)

    facade.increment("a", method="GET")
    facade.set_gauge("b", 2)
    facade.observe("c", 0.5)

    assert sink.calls == [
        ("inc", "a", 1.0, {"method": "GET"}),
        ("gauge", "b", 2, {}),
        ("obs", "c", 0.5, {}),
    ]
