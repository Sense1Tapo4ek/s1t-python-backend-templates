---
status: accepted
date: 2026-06-08
---
# 0023 - Dissolve the standalone metrics context into shared

## Context
An earlier decision (since removed from the log) promoted metrics to a top-level context with a by-name facade
(`increment`/`set_gauge`/`observe`), three demo metrics, a `/metrics-demo`
endpoint, and an ACL example (`db_example_sddd` -> metrics). In practice the
by-name facade added indirection for no payoff: `/metrics` is always-on infra,
and custom metrics read clearer as module-level `prometheus_client` constants
declared where the measurement happens.

## Decision
Delete the `metrics` context. Move the `/metrics` endpoint builder, the
multiprocess bootstrap, and `MetricsConfig` into `shared`
(`shared/adapters/metrics.py`, `shared/config.py`). Custom metrics become
module-level `Counter`/`Gauge`/`Histogram` in the owning adapter (e.g.
`videos_uploaded_total` in `media_example`). Drop the by-name facade, the demo
endpoint, and the metrics ACL example.

## Consequences
- + Less indirection; a metric lives next to the code it measures.
- + `/metrics` is plain shared infra, composed unconditionally.
- - Loses the worked by-name-facade + ACL example (ACL still covered by the
    S-DDD ruleset and the deleted context's git history).
- - Module-level collectors need REGISTRY snapshot/restore in e2e tests that
    build their own app.

## Alternatives considered
- Keep the standalone context - over-engineered for always-on infra; rejected.
- Keep the facade, move it to shared - the by-name indirection was the part
  not earning its keep; rejected.
