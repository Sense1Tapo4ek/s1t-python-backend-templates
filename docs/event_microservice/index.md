# event_microservice

Audience: contributor working on the event-driven worker.

Standalone uv service: a FastStream consumer that reads the `video_uploaded`
Valkey Stream and fans heavy work out to SAQ jobs, joined in Valkey. Shares no
code with `litestar_backend` -- only the wire contract (see
[../architecture.md](../architecture.md)).

Status: fully implemented. The `media_processing` context, the three SAQ
execution models, and the Valkey join are live. The full loop is closed:
return events flow back to `litestar_backend` over the `video_status` stream
(see [../contract/video_status.md](../contract/video_status.md)).

## Layout

- `src/root/` -- composition (Dishka container) + two entrypoints:
  `consumer` (FastStream app) and `saq_worker` (SAQ settings).
- `src/shared/` -- own Valkey client, structlog setup, base errors/config.
- `src/media_processing/` -- the bounded context: domain (JobKind, JoinPolicy), app (use cases), ports (facade, Valkey join store, SAQ queue), adapters (FastStream consumer, 3 SAQ jobs).

## Run

```bash
docker compose up event_microservice        # FastStream consumer
docker compose run --rm event_microservice_test
```
