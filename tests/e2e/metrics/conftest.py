"""E2E fixtures for the metrics context.

Under prometheus_client multiprocess mode the relevant isolation state is
the PROMETHEUS_MULTIPROC_DIR mmap directory, NOT the global REGISTRY.
Each test module that needs its own Litestar app must set
PROMETHEUS_MULTIPROC_DIR (and VOLUME_PATH) via monkeypatch before calling
create_app(), so the env is inherited by the metric definitions.

The REGISTRY snapshot/restore present in the old conftest is removed:
  - Under multiproc mode metrics are written to mmap files, not to the
    in-process REGISTRY.  The REGISTRY contains only the multiprocess
    collector stub; unregistering it between tests causes more problems
    than it solves.
  - PrometheusMiddleware._metrics is a ClassVar that caches Counter/
    Histogram/Gauge instances by name.  Across multiple create_app()
    calls in the same process the same metric objects are reused (the
    "if metric_name not in _metrics" guard is a no-op on the second
    call).  This is correct behaviour: the counters just keep
    accumulating, which is exactly what we assert against in the e2e
    tests.
"""
