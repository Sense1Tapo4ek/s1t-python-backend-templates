# Feature map: video pipeline

How a video upload travels through both services and comes back as a live
status update. Entry point only -- every fact lives on the linked pages.

## Flow

```
        litestar_backend                          event_microservice
+------------------------------+        +----------------------------------+
| POST /videos                 |        |  FastStream consumer             |
|   video row + outbox row     |        |    (consumer group, dedup inbox) |
|   (one transaction)          |        |            |                     |
|        |                     |        |            v                     |
|        v                     |        |  SAQ jobs (fan-out)              |
|  OutboxRelay (lifespan task) |        |    stt / plagiarism /            |
|        |                     |        |    transcode                     |
|        v                     |        |            |                     |
|  ==== video_uploaded ====================>         v                    |
|      (Valkey Stream)         |        |  join store (all jobs done?)     |
|                              |        |            |                     |
|  status consumer (lifespan)  |        |            v                     |
|        ^                     |        |  event publisher                 |
|  <=== video_status =====================           |                    |
|        |     (Valkey Stream) |        +----------------------------------+
|        v                     |
|  Video status machine        |
|        |                     |
|        v                     |
|  SSE feed  GET /videos/feed  |
+------------------------------+
```

## Service roles

| Participant | Owns |
|:---|:---|
| `litestar_backend` / media_example | Upload endpoint, the Postgres system of record, the transactional outbox, the status machine, the SSE feed. |
| `video_uploaded` stream | Forward transport: upload notifications, at-least-once via outbox + relay. |
| `event_microservice` / media_processing | Consuming uploads idempotently, fanning work out to SAQ jobs, joining results, publishing status events. |
| `video_status` stream | Return transport: processing-status notifications back to the backend. |

## Where the facts live

| Question | Page |
|:---|:---|
| Wire shape of the forward stream | [contract/video_uploaded.md](../contract/video_uploaded.md) |
| Wire shape + delivery guarantees of the return stream | [contract/video_status.md](../contract/video_status.md) |
| Backend context internals (outbox, status machine, SSE) | [media_example](../../src/litestar_backend/docs/contexts/media_example.md) |
| Worker context internals (consumer, jobs, join) | [media_processing](../../src/event_microservice/docs/contexts/media_processing.md) |
| Cross-service topology + invariants | [architecture.md](../architecture.md) |
| Why streams carry notifications, DB stays truth | [ADR 0022](../adr/0022-video-pipeline-transport-roles.md) |
| Why two services, no shared code | [ADR 0026](../adr/0026-two-service-monorepo.md) |
| Why the return path skips the outbox | [ADR 0028](../adr/0028-video-status-return-path.md) |
| SAQ execution models in the worker | [ADR 0027](../../src/event_microservice/docs/adr/0027-saq-execution-models.md) |
