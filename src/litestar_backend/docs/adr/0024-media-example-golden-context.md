---
status: accepted
date: 2026-06-08
---
# 0024 - media_example is the single golden context

## Context
The template carried two partial examples: `orders` (event showcase, at-most-
once, no durability) and `db_example_sddd` (raw asyncpg, pooled vs
per-request variants). Neither showed a production-grade async
pipeline, and maintaining both plus the realtime story was redundant overlap.

## Decision
Replace both with one golden context, `media_example`: raw asyncpg pool, a
transactional outbox + relay to a Valkey Stream, a Litestar SSE feed, full
S-DDD layering (domain/app/ports/adapters), and the full test pyramid
(unit/flow/integration/e2e). It is the primary worked reference;
`db_example_litestar` stays only as the SQLAlchemy / advanced-alchemy variant.

The data-layer clause above is revised in part by
[ADR 0025](0025-standardize-on-sqlalchemy.md): `media_example` runs on plain
SQLAlchemy 2.0, not raw asyncpg. The rest of this decision stands.

## Consequences
- + One coherent end-to-end example instead of two partial ones; shows outbox /
    at-least-once, asyncpg, Valkey, and SSE together.
- + The realtime story and the asyncpg story merge into one
    context a reader can follow top to bottom.
- - A single context cannot show the pooled-vs-per-request contrast sddd taught
    (acceptable -- it was infra trivia, not domain insight).
- - More surface than `orders` had; the outbox + relay add moving parts (their
    roles are recorded in ADR 0022).

## Alternatives considered
- Keep orders + db_example_sddd, add media as a third - three overlapping
  examples to maintain; rejected.
- Build media on SQLAlchemy - `db_example_litestar` already covers that stack;
  raw asyncpg keeps the outbox/relay mechanics visible; rejected.
