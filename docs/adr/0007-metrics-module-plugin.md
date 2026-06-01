# 0007 — Metrics use a module plugin contract, not direct controllers
Status: superseded by 0010
Date: 2026-05-12

## Context
We need a Prometheus endpoint and an admin dashboard. The dashboard must show
multiple subsystems (HTTP, logs, process). Other contexts (auth, future
modules) will add their own panels. Centralising the rendering in
`admin/metrics` would force every new context to touch this folder.

## Decision
`admin/metrics` defines `IMetricsModulePlugin` in its `app/interfaces/`. Each
context owning a signal exposes a plugin under
`<context>/ports/driven/plugins/`. Dishka multi-provide collects them into
`list[IMetricsModulePlugin]`; an in-memory registry indexes by `slug`. The
admin/metrics context renders overview + detail by iterating the registry.

## Consequences
- + Adding a module is local to the producing context. No `admin/metrics`
  edits required.
- + Same Valkey snapshot drives Prometheus aggregation and the UI — single
  source of truth.
- − Cross-cutting changes (e.g., severity model) require updating every
  plugin; mitigated by keeping the contract small (3 methods).
- − Dishka multi-provide is implicit; new contributors must read this ADR or
  `docs/contexts/admin-metrics.md` to discover the wiring.

## Alternatives considered
- **One controller per subsystem in `admin/metrics`** — couples this context
  to every other one; rejected.
- **Pure Prometheus + Grafana, no in-app UI** — adds a runtime dependency;
  rejected, small ops want one URL.
- **Event-bus driven module registration** — overkill for a static plugin set
  resolved at boot; rejected.
