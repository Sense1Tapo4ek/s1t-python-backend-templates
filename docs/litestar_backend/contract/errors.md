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
  "status": 409,
  "type": "urn:litestar-base:error:empty-item-name",
  "title": "Conflict",
  "detail": "item name must not be empty",
  "instance": "/db-example-sddd/pooled/items"
}
```

There are two body shapes behind the single media type, distinguished by the
presence of `type`:

- **Application errors** (`LayerError` subtypes -> 409/404/422/503/500):
  `type` present, `title` = short status phrase (`"Conflict"`, `"Not Found"`),
  `detail` = the domain/app message on 4xx (a fixed generic string on 5xx),
  `instance` = the request path.
- **Framework/validation errors** (400 and other raw `HTTPException`s):
  **no `type` key, no `instance` key**. `title` carries the offending field
  message (e.g. ``"Object missing required field `name`"``) and `detail` is the
  generic status phrase (`"Bad Request"`). There is no `extra`/`errors` object.

| Field | Semantics |
|:---|:---|
| `type` | Stable, **non-dereferenceable** URN identifying the problem class. Match on it as a string; do **not** HTTP-fetch it. **Present only on application errors** — absent on framework/validation errors. See the registry below. |
| `title` | Short human summary. On application errors it is the status phrase (`"Conflict"`, `"Not Found"`). On a framework/validation error it carries the offending **field message** instead. |
| `status` | The HTTP status code, repeated in the body. Always present. |
| `detail` | On application 4xx: the domain/app message. On 5xx: a fixed generic string — internals never leak. On framework/validation errors: the generic status phrase (e.g. `"Bad Request"`). |
| `instance` | The request path of this occurrence. Present on application errors; **absent on framework/validation errors**. |

Branch your logic on `status` (always present) and, for application errors,
`type`. `type` is absent on framework/validation errors — do not rely on it for
400. Never parse `detail` or `title` — they are prose and may change.

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

## `type` URN registry

Two conventions produce the `type` value:

- **Application errors** (`LayerError` subtypes): derived from the exception
  class name, kebab-cased, under `urn:litestar-base:error:`. Example:
  `EmptyItemName` -> `urn:litestar-base:error:empty-item-name`. 5xx use fixed
  slugs `:service-unavailable` (503) and `:internal` (500).
- **Framework errors**: hand-written stable slugs so the framework class name
  never leaks. Authentication/authorization use
  `urn:litestar-base:error:unauthorized` (401) and
  `urn:litestar-base:error:forbidden` (403).

URNs are identifiers, not URLs. Treat the set as additive: new error classes
add new URNs; existing ones stay stable.

## Worked examples

409 — domain conflict (application error: `type` + `instance` present):

```json
{
  "status": 409,
  "type": "urn:litestar-base:error:empty-item-name",
  "title": "Conflict",
  "detail": "item name must not be empty",
  "instance": "/db-example-sddd/pooled/items"
}
```

400 — validation failure (framework error: no `type`, no `instance`; the field
message lands in `title`, `detail` is the generic status phrase):

```json
{
  "status": 400,
  "title": "Object missing required field `name`",
  "detail": "Bad Request"
}
```

## Pseudo-client

```python
resp = await client.post("/db-example-sddd/pooled/items", json=payload)
if resp.status_code >= 400:
    problem = resp.json()           # application/problem+json
    code = problem["status"]        # always present
    kind = problem.get("type")      # present only on application errors
    if code == 409 and kind == "urn:litestar-base:error:empty-item-name":
        ...                         # handle the specific conflict
    elif code == 400:
        ...                         # validation: no `type`; show problem["title"]
    elif code == 503:
        ...                         # retry / back off; body is generic
    else:
        ...                         # surface problem["title"] to the user
```

## Pointers

- ADR: [adr/0018-rfc9457-problem-details.md](../../adr/0018-rfc9457-problem-details.md).
- Internals: [subsystems/error_hierarchy.md](../subsystems/error_hierarchy.md).
- Schema source: `src/shared/adapters/openapi.py` (`ProblemDetail`).
