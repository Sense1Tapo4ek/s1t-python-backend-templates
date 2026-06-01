# Metrics

> Audience: contributor working in any context that exposes operational data,
> and operator deploying the system.

## Purpose

`GET /metrics` — Prometheus-formatted scrape endpoint. Aggregates per-worker
counters / gauges / histograms via `prometheus_client` native multiprocess
mode. Always on when the metrics context is composed; gated by an admin guard
unless `METRICS_PROM_ENDPOINT_PUBLIC=true`.

There is no admin metrics UI. No external store.

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
| `MetricsConfig` | `admin/metrics/config.py` | env prefix `METRICS_` |
| `GET /metrics` | `ConfiguredPromController` | path configurable |
| `multiproc_dir` | `METRICS_MULTIPROC_DIR` | master sets + wipes at start |

## Invariants & gotchas

- **`PROMETHEUS_MULTIPROC_DIR` set before import.** The master process sets
  this env var from `MetricsConfig.multiproc_dir` and wipes the directory
  before workers start. Workers inherit the env var; `prometheus_client`
  auto-detects multiprocess mode on import.
- **Shard wipe at master start.** Stale `.db` files from a prior run would
  double-count metrics. The master wipes `<multiproc_dir>` before
  `uvicorn.run`. Workers must not pre-import `prometheus_client` before that.
- **`mark_process_dead` on worker stop.** Each worker calls this in its
  lifespan shutdown. Failure is non-fatal; stale shards otherwise persist
  until the next master restart.
- **No Valkey, no external store.** All aggregation is via filesystem shards
  in `<multiproc_dir>`. If the directory is on a tmpfs that survives process
  restart, old shards accumulate; wipe logic in the master guards this.
- **`APP_WORKERS` is unconstrained.** Multiprocess mode scales to any worker
  count without configuration changes.

## How to: expose a custom metric

Register a `prometheus_client` collector in the context that owns the signal.
Do it in a lifespan manager or at module import — not in the DI provider
(providers are lazy and the collector must be registered before the first
scrape).

```python
from prometheus_client import Counter

MY_COUNTER = Counter("my_events_total", "Count of my events", ["label"])
```

The `MultiProcessCollector` picks it up automatically on the next scrape.

## How to: make the endpoint public

Set `METRICS_PROM_ENDPOINT_PUBLIC=true`. Use only inside a trusted network
(VPN, k8s mesh). The admin guard is bypassed; the endpoint is still served
over plain HTTP unless you add TLS termination upstream.

## Pointers

- Context reference: [docs/contexts/admin-metrics.md](../contexts/admin-metrics.md)
- ADR: [docs/adr/0010-prometheus-multiprocess.md](../adr/0010-prometheus-multiprocess.md)
- Litestar Prometheus plugin: upstream `litestar.plugins.prometheus` docs
- `prometheus_client` multiprocess guide: upstream docs
