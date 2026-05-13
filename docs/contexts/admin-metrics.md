# admin/metrics

> Audience: contributor touching the admin/metrics bounded context.

## Purpose

Owns the Prometheus endpoint, the metrics admin UI, and the plugin registry
that lets other contexts surface their own modules on `/admin/metrics`. Does
**not** own any business signals — those are produced by the contexts that
care about them (HTTP middleware in `shared/`, log subsystem in `admin/log/`,
process metrics in `admin/metrics/` itself).

## Mental model

```
admin/metrics/
├── domain/        # severity, VOs, errors (pure)
├── app/
│   ├── interfaces/  # IMetricsModulePlugin, IModulePluginRegistry,
│   │                # IMetricsPublisher, ILoopLagSampler,
│   │                # IRssSampler, IQueueDepthProvider
│   └── use_cases/   # publish_worker_snapshot, render_overview,
│                    # render_module_detail
├── ports/
│   ├── driving/   # msgspec response schemas (JSON polling)
│   └── driven/    # InMemoryModulePluginRegistry, RedisMetricsPublisher,
│                  # ValkeyAggregatedCollector, samplers, plugins/workers
├── adapters/
│   ├── driving/   # PrometheusController subclass, overview + module
│   │              # renderer controller, static assets
│   └── lifespan/  # MetricsLifespanManager (registers collector, runs workers)
├── config.py
└── provider.py
```

The plugin registry is the **only** public surface for cross-context wiring.
A context that wants to appear on the dashboard provides an
`IMetricsModulePlugin` and Dishka collects all of them via the
`list[IMetricsModulePlugin]` multi-provide.

## Public surface

- **Env (`METRICS_…`):**
  - `METRICS_ENABLED` — gates UI only (default `true`)
  - `METRICS_PROM_ENDPOINT_PATH` — Prometheus endpoint path (default `/metrics`)
  - `METRICS_PROM_ENDPOINT_PUBLIC` — bypass admin guard (default `false`)
  - `METRICS_KEY_PREFIX` — Valkey key prefix (default `metrics:`)
  - `METRICS_KEY_TTL_S` — Valkey hash TTL in seconds (default `30`)
  - `METRICS_PUBLISH_INTERVAL_S` — sampler + publisher cadence + UI poll
    (default `5`)
- **Interfaces (in `app/interfaces/`):** consumers import only these.
- **HTTP routes:**
  - `GET /admin/metrics/` (HTML overview)
  - `GET /admin/metrics/{slug}` (HTML detail)
  - `GET /admin/metrics/api?module=…` (JSON snapshot)
  - `GET /metrics` (Prometheus text)
  - `GET /admin/metrics/static/…` (CSS / JS)

## Invariants & gotchas

- **Reserved slugs:** `overview`, `api`, `static`. Registry raises
  `DuplicateSlugError` when violated.
- **Module ordering:** plugins set `order: int`; lowest wins. Tie-breaker is
  slug alphabetical.
- **HTTP middleware lives in `shared/`, not here.** The metrics context owns
  the *exposure*, not the *production*, of HTTP signals.
- **Tests for cross-context plugins go in the consuming context.** The
  `admin/metrics` test suite covers the registry, samplers, collector, and
  rendering. Each context's plugin gets a flow test in its own `tests/flow/`.
- **Schema versioning:** the Valkey snapshot uses string-typed fields. If you
  add fields, plugins must default-safely. Don't break old workers.

## Pointers

- Subsystem doc (rationale + recipes): [docs/subsystems/metrics.md](../subsystems/metrics.md)
- ADR: [docs/adr/0007-metrics-module-plugin.md](../adr/0007-metrics-module-plugin.md)
- Architecture overview: [docs/architecture.md](../architecture.md)
