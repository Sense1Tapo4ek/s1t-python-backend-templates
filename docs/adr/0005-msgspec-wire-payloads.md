# 0005 — msgspec for wire payloads
Status: accepted
Date: 2026-05-06

## Context
Hot paths (SSE log fan-out, NDJSON export, typed event bus) serialize
small dataclass-shaped messages at high frequency. Pydantic's full
validation pipeline is the wrong tool there — it's optimized for HTTP
request validation, not for "encode this trusted internal struct fast".

## Decision
- `msgspec.json` for dataclass-shaped wire payloads (event bus, NDJSON
  export rows, anything internal that crosses a queue or a channel).
- Pydantic — only at HTTP boundaries (request schemas, OpenAPI).
- `orjson` for one-shot JSON encodes inside structlog's logger pipeline.

## Consequences
- + 5–10× faster encode/decode than Pydantic on the hot path; native
  support for `UUID`, `Decimal`, `datetime`, frozen dataclasses.
- + Type-driven decode (`msgspec.json.decode(raw, type=OrderPaidEvent)`)
  reconstructs the exact dataclass on the consumer side.
- − Three serialization libs to keep in mind (msgspec, Pydantic, orjson).
  Mitigated by the rule: pick by where the payload lives (internal vs
  HTTP vs log).

## Alternatives considered
- Pydantic everywhere — slower hot paths; validation cost we don't need
  on trusted internal data.
- Stdlib `json` — no typed decode, no native `Decimal` / `UUID`.
- Protobuf / FlatBuffers — schema cost too high for an internal event
  bus that doesn't cross processes yet.
