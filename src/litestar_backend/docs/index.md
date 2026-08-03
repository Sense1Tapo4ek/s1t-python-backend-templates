# litestar_backend

Audience: contributor working on the HTTP API service.

Litestar 2.24+ app, strict S-DDD per bounded context, Dishka DI. Owns
Postgres, the admin UI (Jinja), role-based auth (JWT + API keys + static
admin token), Prometheus metrics, and the outbox relay that publishes
`video_uploaded` to the event pipeline. Cross-service topology and wire
contracts live in the root tree: [docs/architecture.md](../../../docs/architecture.md),
[docs/contract/](../../../docs/contract/).

## This tree

- `contexts/` -- one page per bounded context:
  [media_example](contexts/media_example.md) (golden context: outbox, SSE,
  status return path), [auth](contexts/auth.md),
  [admin](contexts/admin.md), [admin-log](contexts/admin-log.md),
  [db_example_litestar](contexts/db_example_litestar.md) (the only
  advanced-alchemy user; owns its own ADR tree under
  [contexts/db_example_litestar/adr/](contexts/db_example_litestar/adr/)).
- `subsystems/` -- cross-cutting concerns inside this service:
  [error_hierarchy](subsystems/error_hierarchy.md),
  [jwt-auth](subsystems/jwt-auth.md), [metrics](subsystems/metrics.md),
  [observability](subsystems/observability.md).
- `infra/` -- service-exclusive technology:
  [dishka](infra/dishka.md), [jinja](infra/jinja.md),
  [openapi](infra/openapi.md), [structlog](infra/structlog.md). Platform
  substrate (Postgres, Valkey) is documented at the root:
  [docs/infra/](../../../docs/infra/).
- `adr/` -- service-scope decisions; see [adr/README.md](adr/README.md).

## Run card

This service's commands: [README.md](../README.md). Repo-wide install and env:
[README.md](../../../README.md) at the root; monorepo dev tooling:
[docs/development.md](../../../docs/development.md).
