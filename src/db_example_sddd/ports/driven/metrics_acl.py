from dataclasses import dataclass

# ACL: the ONLY sanctioned cross-context import in this context -- it adapts
# the metrics context's public facade to this context's IMetrics protocol.
from metrics.ports.driving import MetricsFacade

from ...app import IMetrics


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricsAcl(IMetrics):
    _facade: MetricsFacade

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        self._facade.increment(name, value, **labels)

    def observe(self, name: str, value: float, **labels: str) -> None:
        self._facade.observe(name, value, **labels)
