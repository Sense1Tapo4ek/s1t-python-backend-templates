"""Tear down any test-registered Prometheus collectors between modules.

Each e2e test module builds its own Litestar app (module-scoped
`e2e_client`), which instantiates `HttpMetricsPlugin` and registers
counters/histograms on the global `prometheus_client.REGISTRY`. Without
cleanup, the second module fails with `Duplicated timeseries`.
"""

from collections.abc import Iterator

import pytest
from prometheus_client import REGISTRY


@pytest.fixture(scope="module", autouse=True)
def _isolated_prom_registry() -> Iterator[None]:
    snapshot = set(REGISTRY._collector_to_names.keys())
    yield
    for c in list(REGISTRY._collector_to_names.keys()):
        if c not in snapshot:
            REGISTRY.unregister(c)
