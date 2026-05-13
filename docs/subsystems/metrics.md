# Metrics

> Audience: contributor working in any context that wants to expose
> operational data, and operator deploying the system.

## Purpose

Two surfaces over the same underlying data:

1. **`GET /metrics`** — Prometheus-formatted scrape endpoint. Aggregates
   per-worker counters / gauges / histograms (provided by
   `litestar.plugins.prometheus`) with cross-worker snapshots that workers
   publish to Valkey (RSS, loop lag, queue depth, etc.). Always on when the
   metrics context is composed; gated by an admin guard unless
   `METRICS_PROM_ENDPOINT_PUBLIC=true`.
2. **`/admin/metrics`** — Japandi admin UI: overview cards (one per module) +
   per-module detail pages. Pure presentation over the same Valkey snapshots,
   polled every `METRICS_PUBLISH_INTERVAL_S` seconds. Gated by
   `METRICS_ENABLED`.

The `/metrics` endpoint and the UI are independent: turning the UI off does
not stop publication or scraping.

## Mental model

```
+-----------+   asyncio.gather   +---------------+   HSET <ns>:worker:<id>
| samplers  | -----------------> | publisher_uc  | -------------------+
| (loop,    |   every 5 s        | (app layer)   |                    v
|  rss,     |                    +---------------+              +-------------+
|  qsize,   |                                                   |   Valkey    |
|  http)    |   per worker                                      |  (hashes)   |
+-----------+                                                   +-------------+
                                                                      |
                                                                      | HGETALL / SCAN
                                                                      v
+-----------+   text/plain    +---------------+        +------------------+
|  scraper  | <-------------- | Prometheus    | <----- | aggregated       |
| (k8s,     |                 | controller    |        | collector        |
|  grafana) |                 +---------------+        +------------------+
+-----------+                        ^
                                     | HTML / JSON
                                     v
                              +---------------+
                              | admin UI      |
                              | (overview +   |
                              |  per-module)  |
                              +---------------+
```

- Each worker publishes a snapshot of *its own* per-process metrics under
  `metrics:worker:<host>:<pid>` (TTL `2 × publish_interval_s`). Worker death
  evicts the row automatically.
- HTTP middleware, request counters and latencies live in
  `prometheus_client.REGISTRY` per process and are exposed through Litestar's
  built-in `PrometheusController`.
- The aggregated collector is a custom `prometheus_client.Collector` that
  runs on every scrape: scans `metrics:worker:*`, parses each hash, yields
  gauges with a `worker_id` label.

## Public surface

| Item | Where | Notes |
|:---|:---|:---|
| `MetricsConfig` | `admin/metrics/config.py` | env prefix `METRICS_` |
| `IMetricsModulePlugin` | `admin/metrics/app/interfaces/i_module_plugin.py` | implement to add a module |
| `IModulePluginRegistry` | `admin/metrics/app/interfaces/i_module_registry.py` | resolved from container |
| `GET /metrics` | Litestar `PrometheusController` | path configurable |
| `GET /admin/metrics/` | overview HTML | gated by `enabled` + admin guard |
| `GET /admin/metrics/{slug}` | detail HTML | one per plugin |
| `GET /admin/metrics/api?module=…` | JSON for polling | same gating |

Reserved slugs: `overview`, `api`, `static` (rejected by the registry).

## Invariants & gotchas

- **APP_WORKERS is unconstrained.** Multi-worker Prometheus aggregation works
  through the Valkey-as-shared-registry pattern; never set worker counters
  globally without a `worker_id` label.
- **`enabled=false` gates UI only.** `/metrics` stays up (assuming the
  context is registered). Losing the scrape endpoint hurts more than losing
  the dashboard.
- **Sampler scope.** Loop-lag and RSS samplers are spawned by the request-
  handling process via lifespan. The `log-sink` process publishes its own row
  by spawning the same lifespan from `start_log_sink`.
- **Severity is rendered, not stored.** Plugins decide OK / WARN / BAD from
  raw values on every render. Do not bake thresholds into the publisher.
- **Stale data is shown, not hidden.** If a worker stops publishing its row
  drops out after TTL; the UI shows fewer rows but no "missing" placeholder.
  The Prometheus collector mirrors this — no synthetic zeros.

## How to recipes

### Add a new metrics module

1. In the owning context, create
   `<context>/ports/driven/plugins/<name>_metrics_plugin.py` implementing
   `IMetricsModulePlugin` (slug, name, order, `summary()`, `detail()`,
   `render_detail_html()`).
2. In `<context>/provider.py`, multi-provide it:

   ```python
   @provide(scope=Scope.APP, provides=IMetricsModulePlugin)
   def metrics_plugin(self, deps...) -> IMetricsModulePlugin:
       return MyMetricsPlugin(...)
   ```

3. Run `pytest tests/flow/admin/metrics/` — the contract test
   (`assert_plugin_contract`) catches missing methods, reserved slugs, and
   summary/detail divergence.
4. Done — overview picks the new card up automatically on next render.

### Make the Prometheus endpoint public

Set `METRICS_PROM_ENDPOINT_PUBLIC=true`. Use only inside trusted networks
(VPN, k8s mesh). The guard is bypassed; cardinality limits still apply.

## Pointers

- ADR: [docs/adr/0007-metrics-module-plugin.md](../adr/0007-metrics-module-plugin.md)
- Context reference: [docs/contexts/admin-metrics.md](../contexts/admin-metrics.md)
- Observability page (logs + traces): [docs/subsystems/observability.md](observability.md)
- Infra: [docs/infra/valkey.md](../infra/valkey.md)
- Litestar Prometheus: upstream
  `litestar.plugins.prometheus.PrometheusConfig` docs.
