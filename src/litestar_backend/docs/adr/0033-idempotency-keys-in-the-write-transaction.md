---
status: accepted
date: 2026-08-03
---
# 0033 - Claim idempotency keys inside the write transaction

## Context
`POST /videos` is a non-idempotent write: a client retry after a timeout creates
a second video and a second outbox event. A retry key needs somewhere to live.
Valkey (`SET NX` + TTL) is the cheap option, but the claim and the Postgres
write would then commit separately -- a crash between them leaves a key naming
an effect that does not exist, and every later retry replays a lie.

## Decision
Store keys in a per-context Postgres table (`media.idempotency_keys`, generic
columns in `shared/adapters/driven/postgres/idempotency.py`) and claim them with
`INSERT ... ON CONFLICT DO NOTHING` inside the same `IUoW` transaction as the
video row and the outbox row. The claim carries a snapshot of the created video,
so a replay returns the first response rather than the current state. A
concurrent duplicate blocks on the primary key until the first transaction
resolves, then replays it.

## Consequences
- + A committed key always names a committed effect; the two cannot diverge.
- + No in-flight state to model: an uncommitted claim is invisible, so there is
    no "processing, retry later" branch and no lease to expire.
- + Replay is byte-identical -- the snapshot is the response, not a re-read.
- − A concurrent duplicate waits for the first request instead of failing fast.
- − Retention needs its own sweeper task; the table has no natural TTL.
- − One extra INSERT per keyed write.

## Alternatives considered
- Valkey `SET NX` + TTL -- claim and effect commit separately; rejected.
- Middleware over all POSTs -- the claim leaves the use case's transaction, so
  atomicity is lost for every endpoint; rejected.
- Store only the created id and re-read on replay -- the replayed response
  would differ from the first once the status machine moved on; rejected.
