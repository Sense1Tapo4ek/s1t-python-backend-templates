# event_microservice

Audience: contributor working on the event-driven worker.

Standalone uv service: a FastStream consumer that reads the `video_uploaded`
Valkey Stream and fans heavy work out to SAQ jobs, joined in Valkey. Shares no
code with `litestar_backend` -- only the wire contract (see
[../../../docs/architecture.md](../../../docs/architecture.md)).

The loop is closed in both directions: this service consumes `video_uploaded`
and publishes processing results back to `litestar_backend` over the
`video_status` stream (see
[../../../docs/contract/video_status.md](../../../docs/contract/video_status.md)).

## Layout

- `src/root/` -- composition (Dishka container) + two entrypoints:
  `consumer` (FastStream app) and `saq_worker` (SAQ settings).
- `src/shared/` -- own Valkey client, structlog setup, base errors/config.
- `src/media_processing/` -- the bounded context: domain (JobKind, JoinPolicy), app (use cases), ports (facade, Valkey join store, SAQ queue), adapters (FastStream consumer, 3 SAQ jobs).

## Run card

This service's commands: [README.md](../README.md). Monorepo dev tooling:
[docs/development.md](../../../docs/development.md).
