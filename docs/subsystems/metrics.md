# Metrics

> Audience: contributor working in any context that exposes operational data,
> and operator deploying the system.

## Purpose

`GET /metrics` — Prometheus-formatted scrape endpoint. Aggregates per-worker
counters / gauges / histograms via `prometheus_client` native multiprocess
mode. Always on when the metrics context is composed; gated by an admin guard
unless `METRICS_PROM_ENDPOINT_PUBLIC=true`.

A generic by-name custom-metrics facade (`MetricsFacade.{increment,set_gauge,
observe}`) lets any context emit Counters/Gauges/Histograms without per-metric
plumbing. An unguarded `GET /metrics-demo` endpoint exercises the three demo
metrics. There is no metrics UI. No external store.

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
| `MetricsConfig` | `metrics/config.py` | env prefix `METRICS_` |
| `MetricsFacade` | `metrics/ports/driving/` | by-name `increment`/`set_gauge`/`observe` |
| `GET /metrics` | `prom_controller.py` | path configurable |
| `GET /metrics-demo` | `demo_controller.py` | unguarded demo of all 3 types |
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
- **Gauge uses `multiprocess_mode="livesum"`.** A Gauge is otherwise undefined
  across workers; `livesum` sums live workers' values on scrape.
- **`PrometheusSink` caches metric objects at class level.** Repeated
  `create_app()` (tests) reuse the same series, avoiding `prometheus_client`'s
  duplicate-registration error.

## How to: expose a custom metric

Preferred: call the by-name facade from your context. It creates the underlying
`prometheus_client` object on first use and caches it (see metrics context).

```python
facade.increment("my_events_total", label="x")
facade.observe("my_op_seconds", elapsed)
```

Cross-context, wrap the facade in an ACL — `db_example_sddd` is the worked
example. To register a raw collector directly instead, do it at module import
or in a lifespan manager (not in the lazy DI provider); the
`MultiProcessCollector` picks it up on the next scrape.

## How to: make the endpoint public

Set `METRICS_PROM_ENDPOINT_PUBLIC=true`. Use only inside a trusted network
(VPN, k8s mesh). The admin guard is bypassed; the endpoint is still served
over plain HTTP unless you add TLS termination upstream.

## Pointers

- Context reference: [docs/contexts/metrics.md](../contexts/metrics.md)
- ADR: [docs/adr/0010-prometheus-multiprocess.md](../adr/0010-prometheus-multiprocess.md)
- Litestar Prometheus plugin: upstream `litestar.plugins.prometheus` docs
- `prometheus_client` multiprocess guide: upstream docs
