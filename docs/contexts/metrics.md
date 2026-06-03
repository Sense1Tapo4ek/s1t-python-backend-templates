# metrics context

> Audience: contributor touching the `metrics` bounded context, and operator
> deploying the system.

This is an **example infra context**. The Prometheus scrape is real and
production-usable, but the three demo metrics and the `/metrics-demo` endpoint
are illustrative — delete them (and `demo_controller.py`) once you have your
own signals.

## Purpose

Two jobs:

1. Always-on Prometheus scrape (`GET /metrics`) with RED metrics (rate, errors,
   duration) wired by Litestar's `PrometheusPlugin` middleware. Multi-worker
   safe via `prometheus_client` native multiprocess mode — no external store.
2. A generic by-name custom-metrics API any context can call through a facade:
   `increment` / `set_gauge` / `observe`. No per-metric methods — the facade
   stays decoupled from what is being measured.

## Mental model

```
controller ─▶ MetricsFacade ─▶ IMetricsSink ─▶ PrometheusSink
   (HTTP)      (by-name API)    (Protocol)      (prometheus_client)

GET /metrics ─▶ PrometheusController ─▶ MultiProcessCollector
                                          reads all worker mmap shards
                                          merges → text/plain exposition
```

`MetricsFacade` translates a name + labels into a `prometheus_client` metric
object via `PrometheusSink`, which caches those objects at class level. The
RED HTTP metrics are produced by the `PrometheusPlugin` middleware directly and
need no facade call.

## Public surface

### Facade (`metrics.ports.driving.MetricsFacade`)

- `increment(name, value=1.0, **labels)` — bump a Counter.
- `set_gauge(name, value, **labels)` — set a Gauge.
- `observe(name, value, **labels)` — record into a Histogram.

### Config (`MetricsConfig`, env prefix `METRICS_`)

| Var | Meaning |
|:---|:---|
| `METRICS_PROM_ENDPOINT_PATH` | scrape endpoint path (default `/metrics`) |
| `METRICS_PROM_ENDPOINT_PUBLIC` | bypass admin guard (default `false`) |
| `METRICS_HTTP_BUCKETS` | latency histogram bucket boundaries |
| `METRICS_MULTIPROC_DIR` | dir for mmap shards; defaults to `<VOLUME_PATH>/prometheus` |

### Endpoints

- `GET /metrics` (or the configured path) — Prometheus text exposition, always
  on when the context is composed. Gated by the admin role unless
  `METRICS_PROM_ENDPOINT_PUBLIC=true`.
- `GET /metrics-demo` — unguarded demo endpoint that exercises all three demo
  metrics. Deletable example.

### Demo metrics (deletable)

- Counter `widget_render_total`
- Gauge `widget_queue_depth`
- Histogram `widget_render_seconds`

## Invariants & gotchas

- **A metric name's label set is fixed at first use.** The first `increment`/
  `set_gauge`/`observe` for a name pins its labels; later calls must pass the
  same label keys.
- **Unrelated:** the single-process file-log writer (admin log viewer) is a
  different subsystem; it does not share the multiprocess machinery.

Multiprocess-mode invariants (livesum Gauge, class-level cache, env-var ordering,
shard wipe): [subsystems/metrics.md](../subsystems/metrics.md#invariants--gotchas).

## How to: emit a custom metric from your own context

Resolve `MetricsFacade` through your provider/DI and call it:

```python
facade.increment("orders_created_total", region="eu")
facade.observe("order_total_seconds", elapsed)
```

The name is created on first use; keep the label keys stable across calls.

## How to: emit a metric cross-context (ACL)

A context must not import another context's facade directly. Wrap it in an ACL.
`db_example_sddd` does this as the template's first ACL example:

- `db_example_sddd/app/i_metrics.py` — `IMetrics` protocol (duplicated per the
  S-DDD cross-context rule; the app layer depends on this, not on `metrics`).
- `db_example_sddd/ports/driven/metrics_acl.py` — `MetricsAcl` adapts
  `metrics.ports.driving.MetricsFacade` to `IMetrics`. The only cross-context
  import lives here.

`ItemManagement.create` then calls the injected `IMetrics` to increment
`db_example_items_created_total` and observe `db_example_item_create_seconds`.
See [docs/contexts/db_example_sddd.md](db_example_sddd.md).

## Pointers

- ADR: [0007-metrics-module-plugin.md](../adr/0007-metrics-module-plugin.md) —
  why `prometheus_client` rather than a custom registry (superseded history).
- ADR: [0017-metrics-standalone-context-and-acl-example.md](../adr/0017-metrics-standalone-context-and-acl-example.md)
  — why this split + ACL example.
- ADR: [0010-prometheus-multiprocess.md](../adr/0010-prometheus-multiprocess.md)
  — multiprocess mode.
- Subsystem: [docs/subsystems/metrics.md](../subsystems/metrics.md).
