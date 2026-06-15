# Error model (wire contract)

Purpose: the on-the-wire error envelope for **external consumers** (other
services, agents, SDK authors). Read this to handle any non-2xx response
correctly. The live OpenAPI schema at `/schema` (component `ProblemDetail`)
is the authoritative machine-readable contract; this page is the human
explanation of the shared envelope.

## Media type

Every error response — framework-level (validation, routing) and
application-level — is `application/problem+json`, the RFC 9457
problem-details format. There is one body shape across all status codes.

## Body fields

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
| `type` | Stable, **non-dereferenceable** URN identifying the problem class. Match on it as a string; do **not** HTTP-fetch it. **Present on typed errors** (`LayerError` + auth 401/403) — absent on raw validation (400). See the registry below. |
| `title` | Short human summary. On typed errors it is the status phrase (`"Conflict"`, `"Not Found"`, `"Unauthorized"`). On a raw validation error (400) it is a generic `"Validation failed for <METHOD> <path>"` summary; the per-field messages live in `extra`. |
| `status` | The HTTP status code, repeated in the body. Always present. |
| `detail` | On typed 4xx: the domain/app/auth message. On 5xx: a fixed generic string — internals never leak. On raw validation (400): the generic status phrase (e.g. `"Bad Request"`). |
| `instance` | The request path of this occurrence. Present on typed errors (incl. 401/403); **absent on raw validation (400)**. |
| `extra` | Present **only on raw validation errors (400)**: an array of `{message, key, source}` objects, one per offending field. Absent on typed errors. |

Branch your logic on `status` (always present) and, for typed errors, `type`.
`type` is absent on raw validation (400) — do not rely on it there; read
`extra` instead. Never parse `detail` or `title` — they are prose and may change.

## Observable status codes

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

409 (`DomainError`) and 422 (non-NotFound `AppError`) are defined by the error
model but are not emitted by any built-in endpoint today -- the bundled
endpoints surface 400/401/403/404 and, under failure, 503/500. A new context
that raises a domain conflict or an unprocessable `AppError` makes them
observable; the envelope shape is identical (`type` + `instance` present).

## `type` URN registry

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

## Worked examples

404 — resource not found (application error: `type` + `instance` present):

```json
{
  "status": 404,
  "type": "urn:litestar-base:error:video-not-found",
  "title": "Not Found",
  "detail": "video 3fa85f64-5717-4562-b3fc-2c963f66afa6 not found",
  "instance": "/videos/3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

400 — validation failure (raw validation: no `type`, no `instance`; the
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

## Pseudo-client

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

## Pointers

- ADR: [adr/0018-rfc9457-problem-details.md](../../adr/0018-rfc9457-problem-details.md).
- Internals: [subsystems/error_hierarchy.md](../subsystems/error_hierarchy.md).
- Schema source: `src/shared/adapters/openapi.py` (`ProblemDetail`).
