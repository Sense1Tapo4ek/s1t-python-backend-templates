# 0020 — Use Litestar's in-process event bus + Channels for the realtime context
Status: superseded by 0024
Date: 2026-06-04

## Context
The `orders` context (Phase 1 of the event-driven showcase) needs to fan one
domain action out to side effects (audit/metrics) and a live client feed. We
want to teach event-driven wiring without pulling in a message broker yet, and
without inventing custom infrastructure.

## Decision
Use Litestar-native transports only: `litestar.events` (`@listener` +
`app.emit`, `SimpleEventEmitter`) for the in-process bus, and
`litestar.channels` with `RedisChannelsStreamBackend(history=0)` for the
cross-process SSE feed. The app/ports layers stay framework-free via a local
`_Emitter` Protocol; composition injects the Litestar app as the emitter.

## Consequences
- + Zero extra framework: both transports ship with Litestar; Redis is the
  only new dependency (also shared infra for Phases 2-3).
- + Clean teaching contrast for at-least-once transports added later.
- − In-process bus is at-most-once and process-local; Channels (history=0)
  replays no backlog. A crash between commit and emit loses the event.
- − No transactional outbox; durability is explicitly out of scope here.

## Alternatives considered
- Message broker (FastStream/Redis Streams) now — deferred to Phase 3
  (`streaming_faststream`), which teaches consumer groups + DLQ.
- Task queue (SAQ) for the side effects — deferred to Phase 2 (`jobs_saq`).
- Transactional outbox in Phase 1 — over-scoped for an in-process showcase.
