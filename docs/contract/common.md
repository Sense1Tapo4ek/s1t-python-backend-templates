# Common wire rules

Audience: an **external consumer** of this repo -- a sibling service, an agent,
an SDK author. Everything every endpoint and every stream shares lives here:
address, health, authentication, correlation, the error envelope, and the
compatibility promise. Per-topic pages ([README.md](README.md)) cover only
what is specific to their transport.

## Base address and schema

`litestar_backend` serves everything from one origin; there is no path prefix
and no API version segment. The port is `APP_PORT` (default `8000`).

| Surface | Path |
|:---|:---|
| OpenAPI schema (machine-readable HTTP contract) | `/schema/openapi.json` |
| Swagger UI | `/schema/swagger` |
| Prometheus scrape | `/metrics` (`PROM_ENDPOINT_PATH`) |

The HTTP API is contracted by the generated OpenAPI schema, not by hand-written
pages. This page owns only what the schema cannot express: the error envelope,
the credential families, and the correlation header.

## Health

| Endpoint | Semantics |
|:---|:---|
| `GET /health` | Liveness. Always 200 while the process is up. Body carries build metadata: `status`, `app`, `commit`, `branch`, `dirty`, `started_at`. |
| `GET /health/ready` | Readiness. 200 `{"status": "ready", "checks": {...}}` when the log dir is writable and Postgres and Valkey are reachable; otherwise 503 with the same per-dependency `checks` map under `extra`. |
| `GET /ping` | Minimal liveness. 200 `{"message": "pong"}`. |

Point a liveness probe at `/health` and a readiness/traffic gate at
`/health/ready`. A degraded dependency never takes the process out of
liveness -- only out of readiness.

## Authentication

One credential per request, presented either as `Authorization: Bearer <token>`
or as the `admin_token` cookie (browser surfaces). Three families are accepted
and resolved in order; the first match wins:

| Family | Shape the resolver gates on | Obtained from |
|:---|:---|:---|
| JWT access token | two dots (`a.b.c`) | `POST /auth/token`, rotated via `POST /auth/refresh` |
| API key | `ak_` prefix | `POST /auth/api-keys` (ADMIN) |
| Static admin token | anything else (opaque) | `AUTH_ADMIN_TOKEN` deployment secret |

Resolution never raises: an unknown, expired, revoked, or unverifiable
credential -- including one that cannot be checked because Postgres or Valkey is
down -- yields the anonymous role, fail-closed. Callers therefore see 401, never
a 5xx, when authentication itself fails.

| Situation | `Accept: application/json` | Browser under `/admin/*` |
|:---|:---|:---|
| Anonymous on a protected route | 401 | 303 -> `/admin/login?next=...` |
| Authenticated, insufficient role | 403 | 303 -> `/admin/login?next=...` |

Token lifetimes, claim layout, and revocation semantics live in
[subsystems/jwt-auth.md](../../src/litestar_backend/docs/subsystems/jwt-auth.md).

## Correlation

Every HTTP response carries `X-Trace-Id`. Send your own on the request to join
an existing trace; `X-Request-Id` is accepted as an inbound alias. When neither
header is present the server generates one. The chosen id is echoed on the
response under `X-Trace-Id` regardless of which header supplied it, and it is
bound to every log line the request emits.

Stream events do not carry the HTTP trace id. Cross-service correlation on the
video pipeline keys on `video_id` instead -- see
[features/video-pipeline.md](../features/video-pipeline.md).

## Idempotency

`POST /videos` accepts an optional `Idempotency-Key` request header: an opaque
client-chosen string, 1-255 characters. It is the only endpoint that takes one
today; every other write ignores the header.

Send the same key on every retry of one logical upload. The first request
performs the write and the response carries `Idempotency-Replayed: false`. Any
later request with that key returns the **first response, byte for byte**,
under `Idempotency-Replayed: true` -- the status and body do not drift as the
video moves through its status machine.

| Situation | Result |
|:---|:---|
| No `Idempotency-Key` | Normal write. Every request creates a video; no replay header. |
| New key | 202, the write happens, `Idempotency-Replayed: false`. |
| Known key, same payload | 202, the first body verbatim, `Idempotency-Replayed: true`. |
| Known key, different payload | 422 `urn:litestar-base:error:idempotency-key-reused`. Nothing is written. |
| Empty key | 400 validation error. |
| Concurrent duplicate | The second request waits for the first to commit, then replays it. |

Payload identity ignores JSON key order: re-serialising the same object with
its keys in a different order still replays. Keys are retained for
`MEDIA_IDEMPOTENCY_TTL_SECONDS` (default 24 h); after that the key is forgotten
and a retry would create a second video, so retry inside that window.

## Error model

Every non-2xx response uses the RFC 9457 problem-details envelope. The live
OpenAPI schema at `/schema` (component `ProblemDetail`) is the authoritative
machine-readable form; the rest of this section is the human explanation.

### Media type

Every error response -- framework-level (validation, routing) and
application-level -- is `application/problem+json`, the RFC 9457
problem-details format. There is one body shape across all status codes.

### Body fields

```json
{
  "status": 404,
  "type": "urn:litestar-base:error:video-not-found",
  "title": "Not Found",
  "detail": "video 3fa85f64-5717-4562-b3fc-2c963f66afa6 not found",
  "instance": "/videos/3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

There are two body shapes behind the single media type, distinguished by the
presence of `type`:

- **Typed errors** (`type` + `instance` present): every `LayerError` subtype
  (409/404/422/503/500) plus the auth errors (401 `unauthorized`, 403
  `forbidden`). `title` = short status phrase (`"Conflict"`, `"Not Found"`),
  `detail` = the domain/app/auth message on 4xx (a fixed generic string on 5xx),
  `instance` = the request path.
- **Raw validation errors** (400, the unconverted `HTTPException` path):
  **no `type`, no `instance`**. `title` is a generic
  ``"Validation failed for <METHOD> <path>"`` summary, `detail` is the status
  phrase (`"Bad Request"`), and an `extra` array carries one
  `{message, key, source}` object per offending field.

| Field | Semantics |
|:---|:---|
| `type` | Stable, **non-dereferenceable** URN identifying the problem class. Match on it as a string; do **not** HTTP-fetch it. **Present on typed errors** (`LayerError` + auth 401/403) -- absent on raw validation (400). See the registry below. |
| `title` | Short human summary. On typed errors it is the status phrase (`"Conflict"`, `"Not Found"`, `"Unauthorized"`). On a raw validation error (400) it is a generic `"Validation failed for <METHOD> <path>"` summary; the per-field messages live in `extra`. |
| `status` | The HTTP status code, repeated in the body. Always present. |
| `detail` | On typed 4xx: the domain/app/auth message. On 5xx: a fixed generic string -- internals never leak. On raw validation (400): the generic status phrase (e.g. `"Bad Request"`). |
| `instance` | The request path of this occurrence. Present on typed errors (incl. 401/403); **absent on raw validation (400)**. |
| `extra` | Present **only on raw validation errors (400)**: an array of `{message, key, source}` objects, one per offending field. Absent on typed errors. |

Branch your logic on `status` (always present) and, for typed errors, `type`.
`type` is absent on raw validation (400) -- do not rely on it there; read
`extra` instead. Never parse `detail` or `title` -- they are prose and may change.

### Observable status codes

| Status | Meaning |
|:---|:---|
| 400 | Validation error - malformed or invalid request body/params. |
| 401 | Missing or invalid admin bearer token / cookie. |
| 403 | Authenticated but lacking the required role. |
| 404 | Resource not found. |
| 409 | Domain rule violation (conflict). |
| 422 | Request well-formed but semantically unprocessable. |
| 503 | Downstream/infrastructure dependency unavailable. |
| 500 | Internal server error (generic body; details are server-side only). |

(The 4xx/503 wordings mirror `_ERROR_DESCRIPTIONS` in
`src/shared/adapters/openapi.py`, the source the OpenAPI schema uses.)

409 (`DomainError`) is emitted by `POST /videos/{id}/cancel` when the target is
already terminal (DONE/FAILED) -- the invalid transition raises
`InvalidTransition`. 422 (non-NotFound `AppError`) is emitted by `POST /videos`
when an `Idempotency-Key` is reused with a different payload; any new context
that raises an unprocessable `AppError` adds its own 422, with the same
envelope shape (`type` + `instance` present).

### `type` URN registry

Two conventions produce the `type` value:

- **Application errors** (`LayerError` subtypes): derived from the exception
  class name, kebab-cased, under `urn:litestar-base:error:`. Example:
  `VideoNotFound` -> `urn:litestar-base:error:video-not-found`. 5xx use fixed
  slugs `:service-unavailable` (503) and `:internal` (500).
- **Framework errors**: hand-written stable slugs so the framework class name
  never leaks. Authentication/authorization use
  `urn:litestar-base:error:unauthorized` (401) and
  `urn:litestar-base:error:forbidden` (403).

URNs are identifiers, not URLs. Treat the set as additive: new error classes
add new URNs; existing ones stay stable.

### Worked examples

404 -- resource not found (application error: `type` + `instance` present):

```json
{
  "status": 404,
  "type": "urn:litestar-base:error:video-not-found",
  "title": "Not Found",
  "detail": "video 3fa85f64-5717-4562-b3fc-2c963f66afa6 not found",
  "instance": "/videos/3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

409 -- domain conflict (application error: `type` + `instance` present). Cancelling
a video that is already terminal (DONE/FAILED):

```json
{
  "status": 409,
  "type": "urn:litestar-base:error:invalid-transition",
  "title": "Conflict",
  "detail": "invalid status transition: failed -> failed",
  "instance": "/videos/3fa85f64-5717-4562-b3fc-2c963f66afa6/cancel"
}
```

422 -- idempotency key reused with a different payload (application error):

```json
{
  "status": 422,
  "type": "urn:litestar-base:error:idempotency-key-reused",
  "title": "Unprocessable Entity",
  "detail": "idempotency key 9f1c... was already used with a different payload",
  "instance": "/videos"
}
```

400 -- validation failure (raw validation: no `type`, no `instance`; the
per-field messages land in `extra`, `title` is a generic summary):

```json
{
  "status": 400,
  "title": "Validation failed for POST /videos",
  "detail": "Bad Request",
  "extra": [
    {
      "message": "Object missing required field `source_key`",
      "key": "data",
      "source": "body"
    }
  ]
}
```

### Pseudo-client

```python
resp = await client.delete(f"/videos/{video_id}")
if resp.status_code >= 400:
    problem = resp.json()           # application/problem+json
    code = problem["status"]        # always present
    kind = problem.get("type")      # present only on typed errors
    if code == 404 and kind == "urn:litestar-base:error:video-not-found":
        ...                         # the video does not exist (or was deleted)
    elif code == 400:
        ...                         # validation: no `type`; read problem["extra"]
    elif code == 503:
        ...                         # retry / back off; body is generic
    else:
        ...                         # surface problem["title"] to the user
```

## Stream delivery

The Valkey Streams in [README.md](README.md) share one delivery model:

- **At-least-once.** A consumer may see the same event twice; dedup on the
  payload `event_id`.
- **Ordering is per stream, not global.** Events on one stream arrive in
  publish order; two streams have no relative ordering.
- **Own your inbound schema.** A consumer declares its own struct for the
  payload it reads and never imports the producer's type across the service
  boundary.

## Compatibility

- Field addition is the only non-breaking change. Consumers ignore unknown
  fields; producers never remove or retype a shipped field in place.
- A breaking change bumps the payload `version` and ships alongside a parallel
  consumer, never as an in-place swap.
- The `type` URN set is additive: new error classes add new URNs, existing ones
  stay stable.
- Every wire-shape or semantic change updates the matching contract page in the
  same change. Drift between a contract page and server behaviour is a critical
  bug, not a documentation debt item.

## Pointers

- ADR: [adr/0018-rfc9457-problem-details.md](../../src/litestar_backend/docs/adr/0018-rfc9457-problem-details.md).
- Error internals: [subsystems/error_hierarchy.md](../../src/litestar_backend/docs/subsystems/error_hierarchy.md).
- Auth internals: [contexts/auth.md](../../src/litestar_backend/docs/contexts/auth.md).
- Schema source: `src/shared/adapters/openapi.py` (`ProblemDetail`).
