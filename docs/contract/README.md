# Cross-service contracts

Audience: consumer of a wire protocol this repo speaks — a sibling service,
an agent, an SDK. These pages are the single source of truth; reading the
codebase must never be required to integrate.

This folder holds the contracts shared BETWEEN the two services. One page per
topic family:

| Page | Transport | Producer -> Consumer |
|:--|:--|:--|
| [video_uploaded.md](video_uploaded.md) | Valkey Stream `video_uploaded` | `litestar_backend` -> `event_microservice` |
| [video_status.md](video_status.md) | Valkey Stream `video_status` | `event_microservice` -> `litestar_backend` |

Cross-cutting rules for stream contracts:

- At-least-once delivery; consumers dedup on the payload `event_id`.
- Schema evolution is additive only; `version` bumps only on a breaking
  change and ships with a parallel consumer.
- Each consumer defines its own inbound schema — producer types are never
  imported across the service boundary.

The HTTP API of `litestar_backend` is NOT documented here: its contract is
the auto-generated OpenAPI schema (`/schema/openapi.json`, UI at
`/schema/swagger`). The one hand-rolled piece is the RFC 9457 error envelope:
[errors.md](errors.md).

Any wire-shape change MUST update the matching page in the same PR — drift
between a contract page and server behaviour is a critical bug.
