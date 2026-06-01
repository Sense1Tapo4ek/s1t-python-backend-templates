# admin/metrics

> Audience: contributor touching the admin/metrics bounded context.

## Purpose

Exposes the Prometheus `/metrics` endpoint, wired through Litestar's built-in
`PrometheusController`. Multi-worker safe via `prometheus_client` native
multiprocess mode — no external store required. Does **not** own any business
signals; those are produced by the contexts that care about them (HTTP
middleware in `shared/`, log subsystem in `admin/log/`).

There is no admin metrics UI.

## Mental model

```
master process
  set PROMETHEUS_MULTIPROC_DIR
  wipe stale shards
  uvicorn.run(...)
     |
     +-- worker N
     |     MetricsLifespanManager.start()   -- mkdir multiproc_dir
     |     prometheus_client writes mmap shard under multiproc_dir
     |     GET /metrics -> PrometheusController
     |                       -> MultiProcessCollector reads all shards
     |                       -> merged text/plain
     |     MetricsLifespanManager.stop()    -- mark_process_dead(pid)
     |
     +-- worker N+1 (same)
```

The HTTP request-count / latency / in-progress metrics are provided by
Litestar's `PrometheusPlugin` and are multiprocess-compatible out of the box.

## Public surface

- **Env (`METRICS_`):**
  - `METRICS_PROM_ENDPOINT_PATH` — path for the scrape endpoint (default `/metrics`)
  - `METRICS_PROM_ENDPOINT_PUBLIC` — bypass admin guard (default `false`)
  - `METRICS_HTTP_BUCKETS` — latency histogram bucket boundaries
  - `METRICS_MULTIPROC_DIR` — directory for mmap shards; defaults to
    `<VOLUME_PATH>/prometheus`. Set as `PROMETHEUS_MULTIPROC_DIR` in the OS
    environment by the master before workers start.

- **HTTP routes:**
  - `GET /metrics` (or the configured path) — Prometheus text exposition,
    always on when the context is composed. Gated by the admin guard unless
    `METRICS_PROM_ENDPOINT_PUBLIC=true`.

- **No plugin interfaces.** Cross-context plugin registry removed; each
  context registers its own `prometheus_client` collectors directly.

## File tree

```
admin/metrics/
├── adapters/
│   ├── driving/api/prom_controller.py   # ConfiguredPromController factory
│   └── lifespan/metrics_lifespan_manager.py
├── config.py      # MetricsConfig
└── provider.py    # AdminMetricsProvider
```

## Invariants & gotchas

- **`PROMETHEUS_MULTIPROC_DIR` must be set before `import prometheus_client`
  in any worker.** The master sets it from `MetricsConfig.multiproc_dir` and
  wipes existing shards before calling `uvicorn.run`. Workers must not touch
  the directory before the master does.
- **`mark_process_dead` on stop.** `MetricsLifespanManager.stop()` calls
  `multiprocess.mark_process_dead(os.getpid())` so a terminating worker's
  shard is removed from future scrapes. Failure is non-fatal (logged at
  DEBUG).
- **`multiproc_dir` is always resolved.** `MetricsConfig.resolve_multiproc_dir`
  runs on model construction; `multiproc_dir` is always an absolute `Path`
  after that.
- **Endpoint is always on when composed.** There is no `METRICS_ENABLED` flag;
  if `AdminMetricsProvider` is registered, `/metrics` is served. Remove the
  provider to disable.

## Pointers

- Subsystem doc: [docs/subsystems/metrics.md](../subsystems/metrics.md)
- ADR: [docs/adr/0010-prometheus-multiprocess.md](../adr/0010-prometheus-multiprocess.md)
- Architecture: [docs/architecture.md](../architecture.md)
