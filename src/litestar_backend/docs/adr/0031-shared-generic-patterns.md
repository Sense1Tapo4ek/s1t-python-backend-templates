---
status: accepted
date: 2026-07-21
---
# 0031 - Promote outbox, keyset pagination, and event envelope into shared

## Context
The transactional outbox (table + relay), the keyset cursor codec + page
envelope, and the integration-event field set lived inside `media_example`.
The identity slice needs all three; copying them per context would fork
subtle logic (SKIP LOCKED draining, tuple keyset comparison, dedup fields).

## Decision
Move the generic halves into `shared`, contexts keep only their specifics:
`OutboxMixin` + stream-parameterized `OutboxRelay` (postgres/valkey adapters),
`Page[T]` + cursor codec (`generics/pagination.py`), `keyset_older_than`
(postgres), and `IntegrationEvent` base -- `event_id`, `occurred_at`,
`version` -- in `generics/integration_event.py`. `media_example` is re-wired
onto them; the wire gains only the additive `occurred_at` field. The worker
still defines its own inbound schema -- no shared code across services.

## Consequences
- + One implementation of each pattern; identity reuses instead of forking.
- + Every future event carries dedup identity and a version by construction.
- − `shared` grows framework-coupled surface; changes there fan out to all
    consumers and need the full pyramid.

## Alternatives considered
- Copy patterns per context -- divergence of locking/keyset subtleties.
- A separate library package -- overhead unjustified inside one service.
