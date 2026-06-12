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

**`video_processing_started` and `video_processed` — at-least-once.**
`ValkeyEventPublisher._publish` raises `PortError` on a Valkey error. The
exception propagates out of the use case, which causes SAQ to keep the job
unacked and retry it (for `started`) or leaves the XREADGROUP entry unacked for
FastStream redelivery (for `processed`). Duplicate deliveries are handled by
the consumer's status machine: an `InvalidTransition` error on a repeated
transition is caught, logged at WARNING, and the entry is acked (dup absorbed).

**`video_processing_failed` — at-most-once.**
The event is published from SAQ's `after_process` hook, which is not retried.
If the `XADD` fails, `OnJobFailedUC` logs the exception and continues to clear
the join store. A lost `failed` event leaves the video in PROCESSING status
until manual action; the join TTL (`join_ttl_seconds`) bounds the orphan window.

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
[../litestar_backend/contexts/media_example.md](../litestar_backend/contexts/media_example.md),
[../event_microservice/contexts/media_processing.md](../event_microservice/contexts/media_processing.md),
[../adr/0028-video-status-return-path.md](../adr/0028-video-status-return-path.md).
