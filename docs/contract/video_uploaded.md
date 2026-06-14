# Contract: `video_uploaded` (Valkey Stream)

Audience: any service consuming the video-upload event.

Producer: `litestar_backend` (media_example outbox relay, `XADD`).
Consumer: `event_microservice` (consumer group `media_processing`).
Transport: a Valkey Stream named `video_uploaded`. At-least-once.

## Stream entry (outer fields)

Each `XADD video_uploaded * ...` entry carries three fields:

| Field | Type | Meaning |
|:--|:--|:--|
| `event_id` | string (UUID) | the outbox row id; for relay tracing only |
| `event_type` | string | always `"video_uploaded"` |
| `payload` | string (JSON) | the event body, schema below |

The consumer reads `payload` and ignores the outer `event_id` (it dedups on the
`event_id` INSIDE the payload).

## `payload` JSON

| Field | Type | Required | Meaning |
|:--|:--|:--|:--|
| `event_id` | string (UUID) | yes | unique event id; the idempotency key |
| `event_type` | string | yes | `"video_uploaded"` |
| `version` | integer | yes | schema version; `1` today |
| `video_id` | string (UUID) | yes | the uploaded video's id |
| `source_key` | string | yes | object-store key of the upload |
| `uploaded_at` | string (RFC 3339 / ISO 8601, UTC) | yes | upload timestamp |

## Semantics

- **At-least-once**: the relay re-publishes until the broker accepts; consumers
  may see duplicates and MUST be idempotent. The consumer's join is SADD-based,
  so re-processing a video is safe at the completion level.
- **Idempotency key**: payload `event_id`. The consumer deduplicates by `event_id`
  via `ValkeyInboxStore` (marked AFTER fan-out; see
  [../event_microservice/subsystems/delivery-guarantees.md](../event_microservice/subsystems/delivery-guarantees.md)).
- **Versioning**: additive only. A breaking change bumps `version` and ships a
  parallel consumer. Consumers must ignore unknown fields.

## Minimal consumer (pseudocode)

```python
import msgspec

class VideoUploaded(msgspec.Struct, frozen=True, kw_only=True):
    event_id: str
    video_id: str
    source_key: str
    uploaded_at: str
    event_type: str = "video_uploaded"
    version: int = 1

# entry == {"event_id": "...", "event_type": "video_uploaded", "payload": "<json>"}
event = msgspec.json.decode(entry["payload"], type=VideoUploaded)
# dedup on event.event_id, then process event.video_id
```

See also: [../architecture.md](../architecture.md),
[../event_microservice/contexts/media_processing.md](../event_microservice/contexts/media_processing.md).
