# `user_registered` stream

Audience: consumer of the account-creation event feed (a sibling service, a
worker, an analytics pipeline). Producer: `litestar_backend` auth context via
its transactional outbox -- the event commits atomically with the user row.

## Stream entry (outer fields)

Each `XADD user_registered * ...` entry carries three fields:

| Field | Type | Meaning |
|:--|:--|:--|
| `event_id` | string (UUID) | outbox row id; equals the payload `event_id` |
| `event_type` | string | `"user_registered"` |
| `payload` | string (JSON) | the event body, schema below |

## `payload` JSON

| Field | Type | Required | Meaning |
|:--|:--|:--|:--|
| `event_id` | string (UUID) | yes | unique event id; the idempotency key |
| `event_type` | string | yes | `"user_registered"` |
| `version` | integer | yes | schema version; `1` today |
| `occurred_at` | string (RFC 3339 / ISO 8601, UTC) | yes | when the producer staged the event |
| `user_id` | string (UUID) | yes | the created user's id |
| `role` | string | yes | role granted at registration; `"user"` today |

The payload deliberately carries NO email or profile data -- PII stays out of
the stream. A consumer needing profile fields must fetch them through an API
with access control.

## Semantics

- **At-least-once**: the relay re-publishes until the broker accepts;
  consumers may see duplicates and MUST dedup on the payload `event_id`.
- **Versioning**: additive only. A breaking change bumps `version` and ships
  a parallel consumer. Consumers must ignore unknown fields.
- **Ordering**: stream order approximates registration order but is not a
  transactional guarantee; do not build invariants on it.

## Minimal consumer (pseudocode)

```python
import msgspec

class UserRegistered(msgspec.Struct, frozen=True, kw_only=True):
    event_id: str
    occurred_at: str
    user_id: str
    role: str
    event_type: str = "user_registered"
    version: int = 1

# entry == {"event_id": "...", "event_type": "user_registered", "payload": "<json>"}
event = msgspec.json.decode(entry["payload"], type=UserRegistered)
# dedup on event.event_id, then react to event.user_id
```

No consumer ships in this repo today; the stream is the extension point for
welcome-mail / analytics reactions without touching the auth context.
