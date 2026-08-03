---
status: accepted
date: 2026-06-15
---
# 0029 - Layer JWT auth on the static admin token

## Context

The static admin token (ADR 0004) is a single opaque credential with no
expiry, no rotation, and no revocation. The admin surface needs short-lived,
revocable credentials, but the template carries no user/password store -- auth
is role-only.

## Decision

Add JWT (HS256 via `joserfc`) layered on the static token. `POST /auth/token`
mints an access+refresh pair, bootstrapped by the admin credential; the
Principal stays role-only (`sub = role`). The `joserfc` dependency is confined
to `JwtCodec` in `adapters/`; `JwtService` in `ports/` speaks an `IJwtCodec`
Protocol. Revocation is a Valkey denylist keyed by `jti` (TTL = remaining
life), checked on every JWT request. Refresh is one-time rotation: the old
`jti` is denylisted and reuse is rejected. The denylist fails closed.

## Consequences

- + Instant revocation despite short access TTL; refresh-reuse detection.
- + `joserfc` stays out of `ports/`/`app/`; the static path never hits Valkey.
- − Stateful auth: a Valkey outage degrades JWT auth to anonymous (fail-closed).
- − Two credential families to reason about (opaque static + compact JWS).

## Alternatives considered

- PyJWT -- less RFC-complete (JWS/JWE/JWK) than `joserfc`.
- Pure-stateless JWT -- no revocation; a leaked access token lives out its TTL.
- Fail-open on denylist outage -- revoked tokens slip through during an outage.
