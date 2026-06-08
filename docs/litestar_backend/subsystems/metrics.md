# Metrics

> Audience: contributor working in any context that exposes operational data,
> and operator deploying the system.

## Purpose

`GET /metrics` — Prometheus-formatted scrape endpoint. Aggregates per-worker
counters / gauges / histograms via `prometheus_client` native multiprocess
mode. Gated by an admin guard unless `METRICS_PROM_ENDPOINT_PUBLIC=true`.

There is no longer a standalone `metrics` bounded context. The endpoint,
multiprocess bootstrap, and `MetricsConfig` live in `shared`. Custom metrics
are plain `prometheus_client` module-level constants declared in the adapter
that owns the measurement (e.g. `videos_uploaded_total` in `media_example`).

## Mental model — multiprocess mode

```
master process
  os.environ["PROMETHEUS_MULTIPROC_DIR"] = <multiproc_dir>
  wipe <multiproc_dir>/*.db            -- stale shards from last run
  uvicorn.run(app, workers=N)
        |
        +-- worker 1
        |     prometheus_client mmap --> <multiproc_dir>/counter_0.db
        |
        +-- worker 2
        |     prometheus_client mmap --> <multiproc_dir>/counter_1.db
        |
        +-- worker N ...
```

On every `GET /metrics` scrape, `PrometheusController` (backed by
`MultiProcessCollector`) reads all `*.db` shards in `<multiproc_dir>` and
merges them into a single exposition. Workers that have stopped are removed
from the directory when `mark_process_dead(pid)` is called during shutdown.

HTTP request-count, latency histograms, and in-progress counters are
registered by Litestar's `PrometheusPlugin` and are multiprocess-compatible
without extra configuration.

## Public surface

| Item | Where | Notes |
|:---|:---|:---|
| `MetricsConfig` | `shared/config.py` | env prefix `METRICS_` |
| `build_prom_controller(config)` | `shared/adapters/metrics.py` | returns a typed `PrometheusController` subclass |
| `bootstrap_multiproc(config)` | `shared/adapters/metrics.py` | sets `PROMETHEUS_MULTIPROC_DIR`, wipes stale shards |
| `mark_dead()` | `shared/adapters/metrics.py` | calls `mark_process_dead` on shutdown |
| `GET /metrics` | `build_prom_controller` result | path = `METRICS_PROM_ENDPOINT_PATH` |
| `multiproc_dir` | `METRICS_MULTIPROC_DIR` | master sets + wipes at start |

## Adding a custom metric

Declare the collector at module level in the adapter that owns the
measurement. `prometheus_client` registers it on import; `MultiProcessCollector`
picks it up on the next scrape.

```python
from prometheus_client import Counter

VIDEOS_UPLOADED = Counter("videos_uploaded", "Total videos uploaded")

# in the handler:
VIDEOS_UPLOADED.inc()
```

Module-level declaration avoids duplicate-registration errors when
`create_app()` is called more than once in tests (the same object is returned
by the already-imported module).

## Invariants & gotchas

- **`PROMETHEUS_MULTIPROC_DIR` set before import.** The master process sets
  this env var from `MetricsConfig.multiproc_dir` and wipes the directory
  before workers start. Workers inherit the env var; `prometheus_client`
  auto-detects multiprocess mode on import.
- **Shard wipe at master start.** Stale `.db` files from a prior run would
  double-count metrics. The master wipes `<multiproc_dir>` before
  `uvicorn.run`. Workers must not pre-import `prometheus_client` before that.
- **`mark_dead()` on worker stop.** Each worker calls this in its lifespan
  shutdown. Failure is non-fatal; stale shards otherwise persist until the
  next master restart.
- **No external store.** All aggregation is via filesystem shards in
  `<multiproc_dir>`. If the directory is on a tmpfs that survives process
  restart, old shards accumulate; wipe logic in the master guards this.
- **`APP_WORKERS` is unconstrained.** Multiprocess mode scales to any worker
  count without configuration changes.
- **Module-level collectors survive repeated `create_app()`.** A
  `prometheus_client` collector registers once on import; tests that build
  several apps reuse the same series instead of hitting a duplicate-registration
  error. No `REGISTRY` snapshot/restore is needed.

## How to: make the endpoint public

Set `METRICS_PROM_ENDPOINT_PUBLIC=true`. Use only inside a trusted network
(VPN, k8s mesh). The admin guard is bypassed; the endpoint is still served
over plain HTTP unless you add TLS termination upstream.

## Pointers

- `src/shared/adapters/metrics.py` — `build_prom_controller`, `bootstrap_multiproc`, `mark_dead`
- `src/shared/config.py::MetricsConfig` — all `METRICS_` settings
- [docs/adr/0010-prometheus-multiprocess.md](../../adr/0010-prometheus-multiprocess.md) — multiprocess mode decision
- [docs/adr/0023-delete-metrics-context.md](../../adr/0023-delete-metrics-context.md) — why the metrics context was dissolved
- Litestar Prometheus plugin: upstream `litestar.plugins.prometheus` docs
- `prometheus_client` multiprocess guide: upstream docs
