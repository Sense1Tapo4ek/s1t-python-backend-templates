# 0004 — Static bearer/cookie auth for admin surfaces
Status: accepted
Date: 2026-05-06

## Context
The starter must demonstrate the middleware + facade auth pattern (every
connection gets a `Principal`, role guards on controllers, redirect-vs-401
based on `Accept`) without dragging in OAuth, JWT, or a user database.
Real auth is out of scope until a project hits multi-user requirements.

## Decision
A single static admin token resolved from `AUTH_ADMIN_TOKEN`. Accepted
from either `Authorization: Bearer ...` or the `admin_token` cookie set
by the login flow. Cookie is `HttpOnly`, `SameSite=Strict`, `Secure` only
when the request was HTTPS. Empty token in dev disables auth (logged at
boot); empty token in PROD is rejected at startup by `RootConfig`.

## Consequences
- + Minimal surface: one env var, one resolver
  (`StaticTokenResolver`), one middleware.
- + Token-cap (`MAX_TOKEN_LEN=4096`) + constant-time compare bound the
  blast radius of pathological inputs.
- − Single static token per role — no per-user identity, no audit trail
  of who acted.
- − No CSRF token on the login form; mitigated by token knowledge gate
  but must be added when sessions become per-user.
- − No rate-limit on `/admin/login`. Add at the proxy or as middleware
  in any real deployment.

## Alternatives considered
- JWT — needs key rotation, refresh flow; overshoots the starter's job.
- OIDC — separate identity service required.
- Session table in DB — meaningful only once we have users to put in it.
