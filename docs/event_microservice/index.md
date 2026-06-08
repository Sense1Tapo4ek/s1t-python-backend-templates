# event_microservice

Audience: contributor working on the event-driven worker.

Standalone uv service: a FastStream consumer that reads the `video_uploaded`
Valkey Stream and fans heavy work out to SAQ jobs, joined in Valkey. Shares no
code with `litestar_backend` -- only the wire contract (see
[../architecture.md](../architecture.md)).

Status: implemented (slice 2). The `media_processing` context, the three SAQ
execution models, and the Valkey join are live. Return events + SSE broadcast
are Phase C -- see
[../superpowers/specs/2026-06-08-event-microservice-2-service-monorepo-design.md](../superpowers/specs/2026-06-08-event-microservice-2-service-monorepo-design.md).

## Layout

- `src/root/` -- composition (Dishka container) + two entrypoints:
  `consumer` (FastStream app) and `saq_worker` (SAQ settings).
- `src/shared/` -- own Valkey client, structlog setup, base errors/config.
- `src/media_processing/` -- the bounded context (empty until slice 2).

## Run

```bash
docker compose up event_microservice        # FastStream consumer
docker compose run --rm event_microservice_test
```
