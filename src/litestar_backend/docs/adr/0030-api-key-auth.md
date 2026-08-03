---
status: accepted
date: 2026-06-15
---
# 0030 - DB-backed hashed API keys

## Context

JWT access tokens (ADR 0029) are short-lived and need a refresh round-trip.
Machine callers (CI, cron) want a single long-lived credential they can paste
into a config and revoke later. The static admin token (ADR 0004) cannot be
revoked or rotated and there is only one of it.

## Decision

Add ADMIN API keys stored in Postgres, layered into the same composite resolver
between the JWT and static paths. A key is `ak_` + 256 bits of entropy
(`secrets.token_urlsafe(32)`); only its SHA-256 hash is stored. `ApiKeyResolver`
shape-gates on the `ak_` prefix and does one hashed DB read per request.
`/auth/api-keys` (ADMIN-guarded) mints, lists, and revokes keys; the plaintext
is returned once. Revocation is a soft-delete (`revoked_at`); the resolver
filters on active rows. The repo is APP-scope with a self-managed session
because the auth middleware runs before the per-request DI scope exists. A DB
outage surfaces as `PortError` -> middleware fail-closes to anonymous.

## Consequences

- + Runtime-managed, revocable, audited credentials with no user/password store.
- + Prefix gate keeps JWT and static paths off the api-keys table.
- − One DB read per `ak_` request (no cache); fine for a template.
- − A Postgres outage degrades api-key auth to anonymous (fail-closed).

## Alternatives considered

- bcrypt/argon2 hashing -- unnecessary for 256-bit keys; SHA-256 suffices.
- Valkey storage -- no relational audit trail or list query.
- Config-file keys -- no runtime mint/revoke, no per-key metadata.
