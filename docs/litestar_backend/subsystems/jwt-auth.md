# JWT auth

Purpose: how the `auth` context verifies bearer credentials, mints/rotates/
revokes JWT pairs, and how revocation survives across short-lived access
tokens. For contributors touching auth; consumers calling `/auth/*` read the
contract pages.

## Mental model

Every request carries at most one bearer credential (header or `admin_token`
cookie). The middleware always succeeds: it sets a `Principal`, falling back
to anonymous (`Role.UNKNOWN`) on any failure. Authorization is a separate
concern -- `require_role` guards on protected handlers.

```
Authorization: Bearer <token>
        |
   AuthMiddleware  -> facade.authenticate(token)
        |
   CompositeTokenResolver  (first non-None wins)
        |-- JwtTokenResolver   (token has 2 dots: verify + denylist check)
        '-- StaticTokenResolver (opaque: compare_digest vs admin_token)
        |
   Principal | None  ->  Principal(UNKNOWN) on None or PortError (fail-closed)
```

Two credential families coexist: the **static admin token** (bootstrap, opaque)
and **JWT access tokens** (compact JWS, two dots). The shape gate in
`JwtTokenResolver` (`token.count(".") != 2`) routes opaque tokens past the JWT
verifier and the Valkey denylist entirely -- the static path never touches
Valkey.

## Public surface

HTTP (`auth/adapters/driving/api/token_controller.py`):

| Endpoint | Auth | Result |
|:---|:---|:---|
| `POST /auth/token` | `require_role(ADMIN)` | `200` TokenPairResponse |
| `POST /auth/refresh` | none (body bears the proof) | `200` new pair / `401` invalid |
| `POST /auth/revoke` | none | `204` (idempotent) |

`TokenPairResponse`: `access_token`, `refresh_token`, `token_type="Bearer"`,
`expires_in` (access TTL in seconds, default 900).

Claim shape (HS256, `joserfc`): `iss`, `sub`, `role`, `type` (access|refresh),
`jti`, `iat`, `exp`. `verify` checks `iss` match, `type` match, role parse, and
`exp` against the clock.

Env vars (prefix `AUTH_`, `auth/config.py`):

| Var | Default | Meaning |
|:---|:---|:---|
| `AUTH_JWT_SECRET` | unset | HS256 signing secret. Empty disables JWT. |
| `AUTH_JWT_ISSUER` | `litestar-base` | `iss` claim, verified on decode. |
| `AUTH_JWT_ACCESS_TTL_SECONDS` | `900` | Access lifetime (short by design). |
| `AUTH_JWT_REFRESH_TTL_SECONDS` | `1209600` | Refresh lifetime (14 days). |

## Invariants and gotchas

- **Composite order is JWT then static, first non-None wins.** Wired in
  `auth/provider.py`. Order matters only for performance (shape gate skips
  most work), not correctness -- the two families never collide.
- **Revocation is via the denylist, keyed by `jti`, TTL = remaining life.**
  Access tokens are short-lived but not instantly expirable on their own; the
  denylist makes revocation immediate. `revoke_token` and refresh rotation both
  add the old `jti`. Entries self-expire, so the denylist stays bounded.
- **Refresh rotation is one-time.** `refresh_tokens` verifies the refresh
  token, denylists its `jti`, and returns a fresh pair. Replaying the old
  refresh token is rejected (`401`) -- reuse detection.
- **Fail-closed on Valkey outage.** `ValkeyDenylist` raises `PortError` when
  Valkey is unreachable; the middleware catches it and returns anonymous. A
  JWT whose revocation status cannot be checked is treated as unauthenticated.
  The static admin path is unaffected (shape gate, never reaches Valkey).
- **JWT disabled (no secret) -> `POST /auth/token` returns 503.** With no
  `AUTH_JWT_SECRET`, the codec returns `None`; `issue_tokens` raises
  `JwtDisabledError`, mapped to `503 jwt-disabled` by `jwt_disabled_to_problem`.
  Verification of any JWT also yields `None`, so only the static token works.
- **The codec/service split keeps `joserfc` out of `ports/`.** `JwtCodec`
  (adapters) is the only `joserfc` user; `JwtService` (ports) speaks the
  `IJwtCodec` Protocol and owns claim construction + TTL policy.

## How-to

Bootstrap a JWT pair, then use it:

```bash
ADMIN="$AUTH_ADMIN_TOKEN"
PAIR=$(curl -sX POST localhost:8000/auth/token -H "Authorization: Bearer $ADMIN")
ACCESS=$(echo "$PAIR" | jq -r .access_token)
REFRESH=$(echo "$PAIR" | jq -r .refresh_token)

curl -sX POST localhost:8000/auth/token -H "Authorization: Bearer $ACCESS"   # reuse access
curl -sX POST localhost:8000/auth/refresh -d "{\"refresh_token\":\"$REFRESH\"}"
curl -sX POST localhost:8000/auth/revoke  -d "{\"token\":\"$ACCESS\"}"       # 204
```

## Pointers

- `src/auth/adapters/driven/jwt_codec.py` -- `joserfc` HS256 encode/decode.
- `src/auth/ports/driven/jwt_service.py` -- claim shape, TTL, verify policy.
- `src/auth/ports/driven/jwt_token_resolver.py` -- shape gate + denylist check.
- `src/auth/ports/driven/composite_token_resolver.py` -- resolver chain.
- `src/auth/ports/driven/valkey_denylist.py` -- `jti` denylist, TTL, PortError.
- `src/auth/adapters/auth_middleware.py` -- fail-closed entrypoint.
- ADR `docs/adr/0029-jwt-auth.md` -- the decision record.
- ADR `docs/adr/0004-static-bearer-cookie-auth.md` -- the static layer below.
