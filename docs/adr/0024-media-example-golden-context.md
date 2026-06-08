# 0024 - media_example is the single golden context
Status: accepted (data-layer choice revised by 0025: SQLAlchemy, not raw asyncpg)
Date: 2026-06-08

Supersedes 0011, 0020.

## Context
The template carried two partial examples: `orders` (event showcase, at-most-
once, no durability -- ADR 0020) and `db_example_sddd` (raw asyncpg, pooled vs
per-request variants -- ADR 0011). Neither showed a production-grade async
pipeline, and maintaining both plus the realtime story was redundant overlap.

## Decision
Replace both with one golden context, `media_example`: raw asyncpg pool, a
transactional outbox + relay to a Valkey Stream, a Litestar SSE feed, full
S-DDD layering (domain/app/ports/adapters), and the full test pyramid
(unit/flow/integration/e2e). It is the primary worked reference;
`db_example_litestar` stays only as the SQLAlchemy / advanced-alchemy variant.

## Consequences
- + One coherent end-to-end example instead of two partial ones; shows outbox /
    at-least-once, asyncpg, Valkey, and SSE together.
- + The realtime story (0020) and the asyncpg story (0011) merge into one
    context a reader can follow top to bottom.
- - A single context cannot show the pooled-vs-per-request contrast 0011 taught
    (acceptable -- it was infra trivia, not domain insight).
- - More surface than `orders` had; the outbox + relay add moving parts (their
    roles are recorded in ADR 0022).

## Alternatives considered
- Keep orders + db_example_sddd, add media as a third - three overlapping
  examples to maintain; rejected.
- Build media on SQLAlchemy - `db_example_litestar` already covers that stack;
  raw asyncpg keeps the outbox/relay mechanics visible; rejected.
