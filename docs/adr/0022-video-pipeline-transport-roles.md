# 0022 - Three transports with distinct roles in the video pipeline
Status: accepted
Date: 2026-06-08

## Context
`media_example` fans one video ingest out to two consumers: backend processing
(later phases) and a live browser feed. We need to teach which transport gives
which delivery guarantee, and why a single one will not do. ADR 0020 (orders)
published straight from the handler -- at-most-once, lossy on a crash between
commit and emit.

## Decision
Three transports, each with one job:
1. Postgres transactional outbox -- durable hand-off, written in the SAME
   asyncpg tx as the `videos` row. Atomic: state and intent-to-publish commit
   together.
2. Valkey Stream `video_uploaded` -- at-least-once notification to backend
   consumers, fed by the lifespan outbox relay (`FOR UPDATE SKIP LOCKED`).
3. `litestar.channels` (Valkey backend, history=0) -- ephemeral browser SSE
   fan-out. No replay, no durability.
Postgres is the system of record; Valkey is transport only.

## Consequences
- + Each guarantee is explicit and teachable; outbox gives at-least-once with
    no broker dependency in Phase A.
- + A lost Valkey event is survivable -- the outbox row is the source of truth.
- - Three moving parts for one feature; the relay is a custom lifespan task,
    not a framework primitive.

## Alternatives considered
- One Valkey Stream for backend + browser - couples ephemeral SSE to durable
  delivery; rejected.
- Publish to the Stream directly from the handler (no outbox) - loses
  atomicity, risks phantom/lost events; this was 0020's weakness, rejected.
