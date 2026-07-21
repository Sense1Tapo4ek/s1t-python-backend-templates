# auth

Bearer/cookie authentication for admin surfaces. Three credential families
resolve behind one middleware — JWT, API key, and a static admin token —
plus role-based authorization and redirect-vs-401 selection by `Accept`.

For the *why*, see the ADRs: [0004 static bearer/cookie](../adr/0004-static-bearer-cookie-auth.md),
[0029 JWT](../adr/0029-jwt-auth.md), [0030 API key](../adr/0030-api-key-auth.md).
JWT and API-key depth lives in [subsystems/jwt-auth.md](../subsystems/jwt-auth.md);
this page is the context overview.

## Mental model

Every request gets a `Principal(role, token_id)`. Anonymous callers get
`Role.UNKNOWN` — there is no "no principal" branch downstream. Public
endpoints declare no guard; protected ones declare
`require_role(Role.ADMIN)`.

`AuthMiddleware` reads one bearer credential (header or `admin_token` cookie)
and resolves it through a **composite chain** — order JWT -> API-key ->
static, first non-`None` wins. Each resolver shape-gates first, so a token
reaches at most one verifier: JWT = two dots, API-key = `ak_` prefix, static
= the fallback. The middleware never raises; any failure (incl. Valkey/DB
outage — fail-closed) yields `Role.UNKNOWN`.

```
HTTP request
    │
    ▼
AuthMiddleware ─── reads Bearer header / admin_token cookie
    │              resolves via CompositeTokenResolver → Principal
    │                ├─ JwtTokenResolver     (2 dots: verify + jti denylist)
    │                ├─ ApiKeyResolver       ("ak_": DB lookup by hash)
    │                └─ StaticTokenResolver  (opaque: compare_digest)
    ▼
controller.guards = [require_role(Role.ADMIN)]
    │              UNKNOWN → NotAuthorizedException
    │              wrong role → PermissionDeniedException
    ▼
handler runs
```

## Public surface

| Symbol | Where | Role |
|:---|:---|:---|
| `AuthMiddleware` | `auth/adapters/auth_middleware.py` | Reads token, attaches `Principal` to scope. Never raises; fail-closed. |
| `require_role(Role)` | `auth/ports/driving/guards.py` | Litestar guard factory. Cross-context callable, lives in `ports/driving/`. |
| `AuthFacade` | `auth/ports/driving/` | `authenticate`, token methods, api-key methods, and the user methods (`register`, `login`, `list_users`, `deactivate_user`). |
| `ITokenResolver` | `auth/app/interfaces/` | Resolver contract. `CompositeTokenResolver` chains JWT + API-key + static. |
| `AuthLifespanManager` | `auth/adapters/auth_lifespan_manager.py` | Runs the auth migrations on startup and owns the `user_registered` outbox relay task. |
| `Role`, `Principal` | `shared/domain/auth/` | Cross-cutting kernel types. |

App layer is split `interfaces/` (Protocols) + `use_cases/` (one UC per
action: authenticate, issue/refresh/revoke tokens, generate/list/revoke
api-keys, register/login users, list/deactivate users).

### Endpoints

- `GET /admin/login`, `POST /admin/login` — render form / submit. `LoginController`.
- `POST /admin/logout` — clears cookie, 303 → `/admin/login`.
- `POST /auth/{token,refresh,revoke}` — JWT pair mint / rotate / revoke. `TokenController`.
- `/auth/api-keys` CRUD (POST, GET, DELETE) — ADMIN-guarded. `ApiKeyController`.
- `POST /auth/{register,login}`, `GET /auth/me`, `GET /auth/users` (keyset
  `Page[UserResponse]`), `DELETE /auth/users/{id}` — `UserController`.
  Registration is open; `/me` needs any authenticated role; the users admin
  surface is ADMIN-guarded.

Endpoint contracts (status codes, payload shapes, claim layout) live in
[subsystems/jwt-auth.md](../subsystems/jwt-auth.md).

### Failure mapping

| Situation | API caller (`Accept: application/json`) | Browser under `/admin/*` |
|:---|:---|:---|
| `UNKNOWN` on protected route | 401 | 303 → `/admin/login?next=...` |
| Wrong role | 403 | 303 → `/admin/login?next=...` |

Selection lives in `admin/adapters/driving/error_handlers.py`. The handler
sniffs `Accept` and `path.startswith("/admin")`.

## Cookie auth

`POST /admin/login` accepts `token=<value>&next=<path>`. On success:
- Sets `admin_token` cookie: `HttpOnly`, `SameSite=Strict`, `Secure` only
  when the request was HTTPS.
- 303 → `next` (whitelisted to `/admin/*` to prevent open-redirect).

`ADMIN_COOKIE_NAME` is the single source of truth in `auth/config.py`.

## Database

The context owns a Postgres schema (`auth`, default) holding `api_keys`
(SHA-256 hashes only), `users` (argon2id `password_hash`, role, soft-delete —
the active-email unique index is partial, so a deactivated address can
re-register), and `outbox_messages` (the `user_registered` staging table,
drained by the shared `OutboxRelay`). `AuthLifespanManager`
applies `migrations/auth/` on startup **before** the alchemy and media managers
(see [architecture.md §5](../../../../docs/architecture.md#5-lifespan--startup-ordering)).
The JWT denylist is Valkey-backed, not Postgres. Schema-per-context details:
[infra/postgres.md](../../../../docs/infra/postgres.md).

## Configuration

```
AUTH_ADMIN_TOKEN=<your-secret>     # static admin token (bootstrap)
AUTH_JWT_SECRET=<hs256-secret>     # empty disables JWT issuance + verification
AUTH_JWT_ISSUER=litestar-base      # iss claim, verified on decode
AUTH_JWT_ACCESS_TTL_SECONDS=900    # access lifetime (15 min)
AUTH_JWT_REFRESH_TTL_SECONDS=1209600  # refresh lifetime (14 days)
AUTH_SCHEMA_NAME=auth              # Postgres schema for api_keys
AUTH_POOL_SIZE=5                   # SQLAlchemy pool for the auth engine
```

- `AUTH_ADMIN_TOKEN` empty in `dev` → auth disabled, warning logged at startup.
  UNKNOWN principals still get 401/redirect on protected routes.
- `AUTH_ADMIN_TOKEN` empty in `PROD` → `RootConfig._validate_prod_invariants`
  rejects boot.
- `AUTH_JWT_SECRET` empty → JWT verify yields `None` and `POST /auth/token`
  returns `503`; only the static + api-key paths work.

## Invariants & gotchas

- `AuthMiddleware` runs on **every** request, including public ones —
  attaching `Principal` is its only job.
- The middleware never raises. Authorization belongs to `require_role`.
- `MAX_TOKEN_LEN = 4096` caps input before `compare_digest` to prevent
  pathological-length sinks.
- CSRF protection (Litestar `CSRFConfig`) is enforced on `/admin/*` only:
  admin forms carry `_csrf_token`; every other path is excluded because API
  clients authenticate per-request with bearer credentials. `CSRF_SECRET` is
  required in PROD (per-process random otherwise breaks multi-worker).
- Credential endpoints (`POST /auth/login|register`, `/admin/login`) are
  rate-limited (`RATE_LIMIT_PER_MINUTE`, default 20) with counters in Valkey,
  so the cap holds across workers. Behind a proxy, add client-IP middleware
  or the limit keys on the proxy's address.
- Deactivating a user blocks login and refresh immediately; already-issued
  access tokens live out their TTL (<= 15 min). Unknown-email logins burn a
  dummy argon2 verify so timing does not leak account existence.

## Recipes

### Add a role

```python
# shared/domain/auth/role.py
class Role(StrEnum):
    UNKNOWN = "unknown"
    ADMIN = "admin"
    OPERATOR = "operator"   # new
```

Update `ITokenResolver` implementations to map their tokens to it.

### Protect a controller

```python
from auth.ports.driving import require_role
from shared.domain.auth import Role

class MyController(Controller):
    path = "/foo"
    guards = [require_role(Role.ADMIN)]
```

### Swap / extend the resolver

Implement `ITokenResolver` in `auth/ports/driven/`, then add it to the
`CompositeTokenResolver` chain in `auth/provider.py::AuthProvider`. The
middleware, facade, and use cases stay unchanged. Existing resolvers
(JWT, API-key, static) are the reference shape-gate pattern.

## Pointers

- ADRs: [0004 static](../adr/0004-static-bearer-cookie-auth.md),
  [0029 JWT](../adr/0029-jwt-auth.md), [0030 API key](../adr/0030-api-key-auth.md)
- Subsystem: [subsystems/jwt-auth.md](../subsystems/jwt-auth.md) (JWT + API-key depth)
- Code: `src/auth/`, `src/admin/adapters/driving/api/login_controller.py`
- Related: [contexts/admin.md](admin.md)
