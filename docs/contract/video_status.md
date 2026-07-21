# Contract: `video_status` (Valkey Stream)

Audience: any service consuming video processing status events.

Producer: `event_microservice` (ValkeyEventPublisher, `XADD`).
Consumer: `litestar_backend` (media_example XREADGROUP lifespan task, group `media_example`).
Transport: a Valkey Stream named `video_status`. At-least-once for
`video_processing_started` and `video_processed`; at-most-once for
`video_processing_failed` (see Delivery semantics below).

## Stream entry (outer fields)

Each `XADD video_status * ...` entry carries three fields:

| Field | Type | Meaning |
|:--|:--|:--|
| `event_id` | string (UUID) | matches the `event_id` inside the payload; for routing/tracing |
| `event_type` | string | one of the three literals below |
| `payload` | string (JSON) | the event body, schema below |

## `payload` JSON

| Field | Type | Required | Meaning |
|:--|:--|:--|:--|
| `event_id` | string (UUID) | yes | unique per event; idempotency / trace id |
| `event_type` | string | yes | `"video_processing_started"`, `"video_processed"`, or `"video_processing_failed"` |
| `version` | integer | yes | schema version; `1` today; additive-only evolution |
| `video_id` | string (UUID) | yes | the video being processed |
| `occurred_at` | string (ISO 8601, UTC) | yes | wall-clock time the event was emitted |

## Event types and when each fires

| `event_type` | Fires when | Semantics |
|:--|:--|:--|
| `video_processing_started` | after all three SAQ jobs are enqueued (OnVideoUploadedUC) | signals PENDING -> PROCESSING |
| `video_processed` | after the join count reaches fan-out (CompleteJobUC), BEFORE the join key is cleared | signals PROCESSING -> DONE |
| `video_processing_failed` | from the SAQ `after_process` hook when `attempts >= retries` (terminal failure) | signals PROCESSING -> FAILED |

## Delivery semantics

Two independent guarantee layers: producer-side retry and consumer-side
redelivery.

### Producer-side guarantees

**`video_processing_started` -- at-least-once via FastStream redelivery of the
inbound message.**
`OnVideoUploadedUC` runs inside the FastStream `video_uploaded` consumer
(`adapters/driving/uploaded_consumer.py`). A `PortError` from `publish_started`
propagates out of the use case and out of the handler; FastStream leaves the
`video_uploaded` message unacked and redelivers it. On redelivery the jobs are
re-enqueued (the join store tolerates duplicates) and `started` is re-published.

**`video_processed` -- at-least-once via SAQ job retry.**
`CompleteJobUC` runs inside a SAQ job (`adapters/driving/saq_jobs.py`). A
`PortError` from `publish_processed` propagates and fails the job; SAQ retries
it (requires job retries >= 1; `MediaProcessingConfig.job_retries` defaults to
3). On retry the idempotent join re-detects completion and re-publishes.

**`video_processing_failed` -- at-most-once.**
The event is published from SAQ's `after_process` hook
(`root/entrypoints/saq_worker.py`), which is not retried. `OnJobFailedUC` logs
a publish failure and continues to clear the join store. A lost `failed` event
leaves the video in PROCESSING status until manual action; the join TTL
(`join_ttl_seconds`) bounds the orphan window.

### Consumer-side guarantee (independent of the above)

The `litestar_backend` consumer (`media_example/adapters/driving/status_consumer.py`)
uses XREADGROUP with a per-process consumer name. An unacked entry stays in the
Pending Entry List (PEL); entries idle past `MEDIA_STATUS_CLAIM_IDLE_MS` (default
60 s) are adopted by any live consumer via XAUTOCLAIM. Duplicate deliveries are
handled by the status machine: an `InvalidTransition` on a repeated transition is
caught, logged at WARNING, and the entry is acked (dup absorbed).

**FIFO ordering per stream.** Valkey Streams guarantee FIFO within a single
stream, so `video_processing_started` always precedes `video_processed` in
the stream for the same `video_id`.

## Consumer group

| Setting | Value |
|:--|:--|
| Group name | `media_example` |
| Start id | `0` (replay from the beginning on first creation) |
| mkstream | yes (group creation also creates the stream if absent) |
| Consumer name | `media_example-<hostname>-<pid>` (unique per process) |
| Stale entry recovery | `XAUTOCLAIM` with `min_idle_time = status_claim_idle_ms` (default 60 s) |

NOGROUP errors (stream deleted externally) are self-healed: the consumer
recreates the group and resumes on the next drain cycle.

## Minimal consumer (pseudocode)

```python
import msgspec

class VideoStatusEvent(msgspec.Struct, frozen=True, kw_only=True):
    event_id: str
    event_type: str
    video_id: str
    occurred_at: str
    version: int = 1

# entry == {"event_id": "...", "event_type": "...", "payload": "<json>"}
event = msgspec.json.decode(entry["payload"], type=VideoStatusEvent)
# dedup on event.event_id (or rely on idempotent status machine);
# then dispatch on event.event_type
```

See also: [../architecture.md](../architecture.md),
[../../src/litestar_backend/docs/contexts/media_example.md](../../src/litestar_backend/docs/contexts/media_example.md),
[../../src/event_microservice/docs/contexts/media_processing.md](../../src/event_microservice/docs/contexts/media_processing.md),
[../adr/0028-video-status-return-path.md](../adr/0028-video-status-return-path.md).
