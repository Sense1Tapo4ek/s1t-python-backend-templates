# Cross-service contracts

Audience: consumer of a wire protocol this repo speaks -- a sibling service,
an agent, an SDK. These pages are the single source of truth; reading the
codebase must never be required to integrate.

Start with [common.md](common.md): base address, health, authentication,
correlation, the RFC 9457 error envelope, delivery model, and the
compatibility promise. Then read the page for your transport.

| Page | Transport | Producer -> Consumer |
|:--|:--|:--|
| [common.md](common.md) | all | Rules every endpoint and stream shares. |
| [video_uploaded.md](video_uploaded.md) | Valkey Stream `video_uploaded` | `litestar_backend` -> `event_microservice` |
| [video_status.md](video_status.md) | Valkey Stream `video_status` | `event_microservice` -> `litestar_backend` |
| [user_registered.md](user_registered.md) | Valkey Stream `user_registered` | `litestar_backend` -> (no consumer yet) |

The HTTP API of `litestar_backend` has no hand-written page here: its contract
is the generated OpenAPI schema (`/schema/openapi.json`, UI at
`/schema/swagger`). The hand-maintained parts of the HTTP wire -- the error
envelope, the credential families, the correlation header -- live in
[common.md](common.md).

End-to-end routing across both services:
[features/video-pipeline.md](../features/video-pipeline.md).
