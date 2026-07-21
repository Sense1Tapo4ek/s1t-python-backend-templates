# JWT auth and API keys

Purpose: how the `auth` context verifies bearer credentials, mints/rotates/
revokes JWT pairs and DB-backed API keys, and how revocation survives across
short-lived access tokens. For contributors touching auth; consumers calling
`/auth/*` read the contract pages.

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
        |-- ApiKeyResolver     (token starts with "ak_": one DB read by hash)
        '-- StaticTokenResolver (opaque: compare_digest vs admin_token)
        |
   Principal | None  ->  Principal(UNKNOWN) on None or PortError (fail-closed)
```

Three credential families coexist: the **static admin token** (bootstrap,
opaque), **JWT access tokens** (compact JWS, two dots), and **API keys**
(opaque, `ak_` prefix). Each resolver shape-gates first so a token reaches at
most one verifier: `JwtTokenResolver` only acts on two-dot tokens,
`ApiKeyResolver` only on `ak_`-prefixed tokens, and `StaticTokenResolver`
compares the rest. The static path never touches Valkey; the API-key path
never touches Valkey or the JWT codec.

## Public surface

HTTP (`auth/adapters/driving/api/token_controller.py`):

| Endpoint | Auth | Result |
|:---|:---|:---|
| `POST /auth/token` | `require_role(ADMIN)` | `200` TokenPairResponse (role-only pair) |
| `POST /auth/login` | none (credentials in body) | `200` user-bound pair / `401` uniform on any bad credential |
| `POST /auth/refresh` | none (body bears the proof) | `200` new pair / `401` invalid |
| `POST /auth/revoke` | none | `204` (idempotent) |

`TokenPairResponse`: `access_token`, `refresh_token`, `token_type="Bearer"`,
`expires_in` (access TTL in seconds, default 900).

Claim shape (HS256, `joserfc`): `iss`, `sub`, `role`, `type` (access|refresh),
`jti`, `iat`, `exp`. `verify` checks `iss` match, `type` match, role parse, and
`exp` against the clock. `sub` is the user's UUID for login-minted pairs and
`role.value` for role-only pairs (`/auth/token`); only a user-identifying
`sub` surfaces as `VerifiedToken.subject` / `Principal.subject`. Refresh of a
user-bound pair re-checks the user is active, so deactivation cuts rotation
while old tokens are still unexpired.

Env vars (prefix `AUTH_`, `auth/config.py`) are documented once on the
context page: [contexts/auth.md — Configuration](../contexts/auth.md#configuration).

## Invariants and gotchas

- **Composite order is JWT -> API-key -> static, first non-None wins.** Wired
  in `auth/provider.py`. Order matters only for performance (shape gate skips
  most work), not correctness -- the three families never collide.
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

## API keys

Long-lived ADMIN credentials backed by a Postgres table, for machine callers
(CI, cron) that cannot run the JWT refresh dance. A key is an opaque string
with an `ak_` prefix; only its SHA-256 hash is stored.

HTTP (`auth/adapters/driving/api/api_key_controller.py`), all ADMIN-guarded:

| Endpoint | Result |
|:---|:---|
| `POST /auth/api-keys` | `201` CreatedApiKeyResponse (plaintext shown ONCE) |
| `GET /auth/api-keys` | `200` list of active keys (never the secret) |
| `DELETE /auth/api-keys/{id}` | `204` / `404` if no active key with that id |

`CreatedApiKeyResponse`: `id`, `name`, `api_key` (plaintext), `role`.
`ApiKeyResponse` (list): `id`, `name`, `role`, `created_at` -- no secret.

Invariants and gotchas:

- **SHA-256 at rest, no KDF.** The key carries 256 bits of entropy
  (`secrets.token_urlsafe(32)`), so a plain hash is a safe at-rest form -- the
  keyspace is not brute-forceable, unlike a human password. No bcrypt/argon2.
- **`ak_` prefix gate.** `ApiKeyResolver` only reads the DB for tokens starting
  with `ak_`; JWTs and the static token never hit the api-keys table.
- **One DB read per `ak_` request, no cache.** `find_active_by_hash` hashes the
  presented key and looks up the active row. Acceptable for a template; a busy
  deployment would add a short-TTL cache.
- **Revocation is a soft-delete.** `DELETE` flips `revoked_at`; the key stops
  authenticating immediately (the resolver filters on active rows) but the row
  stays for audit. Revoking a missing/already-revoked id is `404`.
- **Fail-closed on Postgres outage.** A DB error surfaces as `PortError`; the
  middleware catches it and returns anonymous -- same fail-closed path as the
  JWT denylist. An `ak_` request whose key cannot be checked is unauthenticated.
- **Resolver reads outside request scope.** The resolver and its repo are
  APP-scope with a self-managed session, because the auth middleware runs before
  the per-request DI scope exists.

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

Mint an API key with the admin token, then use it (plaintext shown once):

```bash
ADMIN="$AUTH_ADMIN_TOKEN"
KEY=$(curl -sX POST localhost:8000/auth/api-keys -H "Authorization: Bearer $ADMIN" \
      -d '{"name":"ci"}' | jq -r .api_key)                                  # ak_...

curl -s localhost:8000/auth/api-keys -H "Authorization: Bearer $KEY"        # 200, lists keys
ID=$(curl -s localhost:8000/auth/api-keys -H "Authorization: Bearer $ADMIN" | jq -r '.[0].id')
curl -sX DELETE localhost:8000/auth/api-keys/$ID -H "Authorization: Bearer $ADMIN"  # 204
```

## Pointers

- `src/auth/adapters/driven/jwt_codec.py` -- `joserfc` HS256 encode/decode.
- `src/auth/ports/driven/jwt_service.py` -- claim shape, TTL, verify policy.
- `src/auth/ports/driven/jwt_token_resolver.py` -- shape gate + denylist check.
- `src/auth/ports/driven/api_key_resolver.py` -- `ak_` gate + hash lookup.
- `src/auth/ports/driven/sql_api_key_repo.py` -- self-session APP-scope repo.
- `src/auth/ports/driven/composite_token_resolver.py` -- resolver chain.
- `src/auth/ports/driven/valkey_denylist.py` -- `jti` denylist, TTL, PortError.
- `src/auth/adapters/auth_middleware.py` -- fail-closed entrypoint.
- ADR `docs/adr/0029-jwt-auth.md` -- the JWT decision record.
- ADR `docs/adr/0030-api-key-auth.md` -- the API-key decision record.
- ADR `docs/adr/0004-static-bearer-cookie-auth.md` -- the static layer below.
