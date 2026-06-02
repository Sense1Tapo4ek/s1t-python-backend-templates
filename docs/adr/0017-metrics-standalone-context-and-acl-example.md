# 0017 - Metrics as a standalone context; first ACL example
Status: accepted
Date: 2026-06-02

## Context
`/metrics` is always-on infra (Prometheus multiprocess scrape), unrelated to
the admin UI's auth/log/dashboard concerns, yet it lived under
`src/admin/metrics`. The template also lacked a worked cross-context (ACL)
example and any custom (non-RED) metric examples.

## Decision
Promote it to a top-level `metrics` context (no `domain/`; infra only) exposing
a generic by-name facade: `increment` / `set_gauge` / `observe`. Ship three
deletable demo metrics (Counter/Gauge/Histogram) and an unguarded
`/metrics-demo` endpoint. Add the first ACL example: `db_example_sddd` emits a
counter + histogram on item create, reaching the metrics facade through
`ports/driven/acl/metrics_acl.py`, with the consumed protocol duplicated in
`app/i_metrics.py` per the S-DDD cross-context rule.

## Consequences
- + Clear infra boundary; reusable by-name metrics API; worked ACL + custom-
    metric reference in the template.
- - One more context; by-name API trades compile-time metric checking for
    decoupling.

## Alternatives considered
- Keep under `admin/` - wrong boundary; metrics is not an admin concern.
- Typed per-metric facade methods - couples the facade to demo metrics and
  defeats cross-context reuse; rejected.
