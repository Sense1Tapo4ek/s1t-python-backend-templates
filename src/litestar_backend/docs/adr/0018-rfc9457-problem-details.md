---
status: accepted
date: 2026-06-02
---
# 0018 - Render all errors as RFC 9457 problem+json

## Context
Error bodies were hand-rolled `{"detail": ...}` payloads, non-standard and
rendered by two separate code paths. Litestar 2.23 ships a problem-details
plugin. We have a `LayerError` hierarchy with per-layer log levels and a 5xx
no-leak rule that must survive any change.

## Decision
Adopt `application/problem+json` (RFC 9457) for every error. Framework
`HTTPException`s auto-convert via
`ProblemDetailsPlugin(enable_for_all_http_exceptions=True)`. `LayerError`
subtypes convert via pure functions in `shared/adapters/problem_details.py`,
registered as **app-level** `exception_handlers` (wrapped through
`problem_handler`), not the plugin's exception map -- the plugin bypasses
`config.exception_handler` for mapped types, which would drop the `instance`
field. 4xx expose `str(exc)`; 5xx use a generic detail and log full context.

## Consequences
- + Standard, machine-readable errors; populates OpenAPI; single render path.
- + `instance` (request path) set centrally in `problem_handler`.
- − One plugin dependency; converters now log; the plugin-map quirk forces
    app-level wiring rather than the plugin's own map.

## Alternatives considered
- Plugin `exception_to_problem_detail_map` for everything -- rejected: drops the
  RFC 9457 `instance` field for mapped exceptions.
- Keep hand-rolled `{"detail"}` handlers -- rejected: non-standard, two render
  paths, no OpenAPI schema.
