---
status: accepted
date: 2026-06-01
---
# 0010 - Prometheus multiprocess mode replaces Valkey cross-worker aggregation; metrics UI removed

## Context
The custom Valkey-backed aggregation (per-worker snapshot hashes, TTL-bounded
keys, aggregated collector, RSS/loop-lag samplers, module-plugin registry, and
admin UI) added significant surface area with a mandatory external dependency.
`prometheus_client` ships native multiprocess support via mmap shards on a
shared filesystem directory (`PROMETHEUS_MULTIPROC_DIR`), covering the same
cross-worker aggregation need without a separate service.

## Decision
Replace the Valkey cross-worker aggregation stack with `prometheus_client`
multiprocess mode. The master process sets `PROMETHEUS_MULTIPROC_DIR`, wipes
stale shards, then starts workers via `uvicorn.run`. Each worker writes to its
own mmap shard; `MultiProcessCollector` merges on every scrape. Remove the
admin metrics UI and module-plugin registry entirely. `/metrics` is always on
when the context is composed.

## Consequences
- + No external service dependency for metrics.
- + `APP_WORKERS` scales freely with no configuration changes.
- + ~500 LoC deleted (registry, samplers, publisher, UI controllers).
- − No in-app dashboard; operators use Grafana or similar.
- − Multiprocess shards require a shared local filesystem (tmpfs/volume);
  not compatible with network filesystems.

## Alternatives considered
- **Keep Valkey, remove UI only** -- still requires an external service;
  rejected because the primary cost was the service dependency.
- **Statsd sidecar** -- adds a second external dependency; rejected.
