---
status: accepted
date: 2026-07-21
---
# 0032 - Store user identity inside the auth context

## Context
JWT and API-key auth (0029, 0030) authenticated a single admin identity; a
production starter needs registered users with DB-backed roles. The identity
data could live in a new bounded context or inside `auth`.

## Decision
Extend `auth`: a `users` table (argon2id hashes via pwdlib, soft-delete,
partial unique active-email index) beside `api_keys` in the auth schema.
Login mints the existing JWT pair with `sub` = user UUID; refresh re-checks
the user is active. Registration commits a `user_registered` event through
the shared outbox in the same transaction (no email in the payload -- PII
stays off the stream). Static admin token remains as break-glass.

## Consequences
- + Login/token/user lifecycles share one schema, one resolver chain, one
    lifespan -- no ACL hop inside the hot login path.
- + Deactivation cuts login + refresh at once; access tokens die by TTL.
- − The auth context grows; if profiles/preferences appear they belong in a
    separate context, not here.
- − No email verification or password reset yet (needs mail infra).

## Alternatives considered
- Separate `identity` context -- a boundary with no distinct invariants;
  every login flow would cross it via ACL.
- Sessions instead of JWT -- rejected earlier (0029) for statelessness.
