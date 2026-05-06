# auth

Bearer/cookie authentication for admin surfaces. Single static token,
role-based authorization, redirect-vs-401 selection by `Accept` header.

For the *why*, see [adr/0004-static-bearer-cookie-auth.md](../adr/0004-static-bearer-cookie-auth.md).

## Mental model

Every request gets a `Principal(role, token_id)`. Anonymous callers get
`Role.UNKNOWN` — there is no "no principal" branch downstream. Public
endpoints declare no guard; protected ones declare
`require_role(Role.ADMIN)`.

```
HTTP request
    │
    ▼
AuthMiddleware ─── reads Bearer header / admin_token cookie
    │              resolves via ITokenResolver → Principal
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
| `AuthMiddleware` | `auth/adapters/middleware/` | Reads token, attaches `Principal` to scope. Never raises. |
| `require_role(Role)` | `auth/ports/driving/guards.py` | Litestar guard factory. Cross-context callable, lives in `ports/driving/`. |
| `AuthFacade` | `auth/ports/driving/` | `authenticate(token) -> Principal`. Used by login flow. |
| `ITokenResolver` | `auth/app/interfaces/` | Swap point for real auth (DB tokens, JWT). Default: `StaticTokenResolver`. |
| `Role`, `Principal` | `shared/domain/auth/` | Cross-cutting kernel types. |

### Endpoints

- `GET /admin/login`, `POST /admin/login` — render form / submit. `LoginController`.
- `POST /admin/logout` — clears cookie, 303 → `/admin/login`.

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

## Configuration

```
AUTH_ADMIN_TOKEN=<your-secret>
```

- Empty in `dev` → auth disabled, warning logged at startup. UNKNOWN
  principals still get 401/redirect on protected routes.
- Empty in `PROD` → `RootConfig._validate_prod_invariants` rejects boot.

## Invariants & gotchas

- `AuthMiddleware` runs on **every** request, including public ones —
  attaching `Principal` is its only job.
- The middleware never raises. Authorization belongs to `require_role`.
- `MAX_TOKEN_LEN = 4096` caps input before `compare_digest` to prevent
  pathological-length sinks.
- No CSRF token on the login form. Token knowledge is the gate; once
  per-user sessions land, CSRF protection becomes mandatory.
- No rate-limit on `/admin/login`. Add at the proxy or as middleware.

## Recipes

### Add a role

```python
# shared/domain/auth/role.py
class Role(str, Enum):
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

### Swap the resolver

Implement `ITokenResolver` in `auth/ports/driven/repos/`, then:

```python
# auth/provider.py::AuthPortBindings
token_resolver = provide(YourResolver, provides=ITokenResolver)
```

The middleware, facade, and use case stay unchanged.

## Pointers

- ADR: [0004-static-bearer-cookie-auth.md](../adr/0004-static-bearer-cookie-auth.md)
- Code: `src/auth/`, `src/admin/adapters/driving/api/login_controller.py`
- Related: [contexts/admin.md](admin.md)
