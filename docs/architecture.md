# Architecture

The decisions and invariants of this project. Read this before adding a
context or changing a layer. Audience: contributors.

For first-run / install instructions, see [README.md](../README.md).

---

## 1. Bounded contexts

Each context lives at `src/<name>/` and owns its data, errors, and public
API.

| Context | Path | Responsibility |
|:---|:---|:---|
| `shared` | `src/shared/` | Cross-cutting kernel: domain types (`Role`, `Principal`), base config, error hierarchy, event bus, db connection, middleware, structlog setup. Imported by every other context; imports nothing from them. |
| `root` | `src/root/` | Entrypoints (`api.py`, `cli.py`) and DI container assembly. The only place that wires providers together. |
| `auth` | `src/auth/` | Bearer/cookie auth: token resolution, `AuthMiddleware`, `require_role` guards. See [contexts/auth.md](contexts/auth.md). |
| `admin` | `src/admin/` | Admin dashboard skeleton: login UI, dashboard shell, build-info panel. See [contexts/admin.md](contexts/admin.md). |
| `admin/log` | `src/admin/log/` | Sub-context: SQLite log store, FTS5 search, SSE tail, NDJSON/CSV export, retention. See [contexts/admin-log.md](contexts/admin-log.md). |

Adding a context: see §8 below.

---

## 2. Layers (S-DDD)

Every context has the same five layers. Rules are non-negotiable; relaxing
them is what kills the template's ability to grow.

```
<context>/
├── domain/              # Pure stdlib. Aggregates, VOs, domain events, domain errors.
├── app/                 # Use cases. Orchestration only — no I/O, no frameworks.
│   └── interfaces/      # Protocol definitions for every driven port.
├── ports/
│   ├── driving/         # Facades + Pydantic schemas (the public API).
│   └── driven/          # Repos, gateways, ACLs (implement app/interfaces).
├── adapters/
│   ├── driving/         # Controllers, consumers, CLI commands.
│   ├── driven/          # DB engines, broker clients, workers.
│   ├── middleware/      # Context-owned ASGI middleware.
│   └── lifespan/        # Lifespan managers (start/stop sequencing).
├── provider.py          # Dishka Provider — the only place mapping concretes to interfaces.
└── config.py            # Pydantic Settings with a unique env_prefix.
```

The full ruleset, including import direction and validation checklists,
lives in `~/.claude/rules/s-ddd_python/`. This file is the project-level
overview; that ruleset is the source of truth.

---

## 3. Error hierarchy

Defined in `src/shared/generics/errors.py`. Each layer raises its own
subtype; adapters catch and map to HTTP.

```
Exception
└── LayerError
    ├── DomainError      → 409 Conflict       (WARNING)
    ├── AppError         → 422 Unprocessable  (WARNING)
    ├── PortError        → 503 Unavailable    (ERROR + traceback)
    └── AdapterError     → 500 Internal       (EXCEPTION)
```

Global mapping is registered in `src/root/entrypoints/api.py::create_app`
via the `exception_handlers` dict. Specialised handlers (`DslSyntaxError`,
`InvalidLogFilterError`, `NotAuthorizedException`, `PermissionDeniedException`,
`ValidationException`) sit ahead of the generic ones — registration order
matters because Litestar resolves the most specific handler.

A 5xx response **never** carries a traceback to the client. In dev,
`debug=True` enables Litestar's debug renderer; in prod, the catch-all
`fallback_500_handler` returns an opaque body.

See [subsystems/error_hierarchy.md](subsystems/error_hierarchy.md) for raise/catch
conventions per layer.

---

## 4. Composition (DI)

Dishka, scoped at `Scope.APP` for everything by default. Each context exports
one `Provider` (and optional `*PortBindings` companion). The root assembly
lives in `src/root/composition/container.py::build_container`.

```python
return make_async_container(
    SharedProvider(channels_plugin=channels_plugin),
    AdminProvider(),
    AdminLogProvider(),
    AdminLogPortBindings(),
    AuthProvider(),
    AuthPortBindings(),
)
```

Rules:
- Root imports only `provider.py` from each context. Never internals.
- Concrete-to-interface mapping happens in the provider, never anywhere else.
- APP-scope graph resolves lazily on the first request — see §6.

For the runtime Dishka API used here, see [infra/dishka.md](infra/dishka.md).
For the *why*, see [adr/0001-dishka-for-di.md](adr/0001-dishka-for-di.md).

---

## 5. Lifespan & startup ordering

`src/root/entrypoints/api.py::lifespan` is the single place that owns
process startup and shutdown.

Order of operations on startup:
1. `RootConfig()` — fail fast on misconfig (PROD without admin token).
2. `snitchbot.init(...)` — crash reporter armed.
3. `build_container(channels_plugin=...)` — providers wired.
4. `configure_structlog(queue)` — JSON logger + queue sink.
5. `event_bus.start()` — typed pub/sub goes live (subscribers register
   their handlers BEFORE this call, never after).
6. `app.state.auth_facade = await container.get(AuthFacade)` — middleware-
   bound singletons resolved once. ASGI middleware runs outside the Dishka
   request scope, so per-request `container.get()` would be wasteful.
7. `LogLifespanManager.start()` — log subsystem (sink worker, cleanup
   worker, broadcast pump) starts last because it depends on everything
   above.

Shutdown unwinds in reverse with each `try/finally` so a single component's
failure never blocks the rest from stopping.

---

## 6. Configuration

Pydantic Settings, one `config.py` per context, unique `env_prefix`.

| File | Prefix | Owns |
|:---|:---|:---|
| `shared/config.py::BaseAppConfig` | `APP_` | `app_name`, `app_env`, `volume_path`, `runtime_path`. |
| `root/config.py::RootConfig` | `APP_` (extends Base) | server bind/port/workers, security CSP/HSTS, prod invariants. |
| `auth/config.py::AuthConfig` | `AUTH_` | `admin_token` (`SecretStr`). |
| `admin/log/config.py::AdminLogConfig` | `LOG_` | retention, batch sizes, max query limit, paths. |

Rules:
- Business logic never reads `os.environ`. Config flows through providers.
- Each `env_prefix` is unique across the project.
- `RootConfig._validate_prod_invariants` enforces `AUTH_ADMIN_TOKEN`
  non-empty in `APP_ENV=prod`.

The contract for environment variables is `.env.example`. Don't commit
`.env`.

---

## 7. Invariants

Things that, if you change them, will break the app silently or in
production.

- **`APP_WORKERS=1`.** The admin/log SQLite writer is per-process. The CLI
  rejects multi-worker starts at boot.
- **APP-scope DI is lazy.** The graph resolves on the first HTTP request.
  Tests must warm DI before any global env-isolation fixture runs (see
  `tests/e2e/conftest.py::e2e_client`).
- **One `ChannelsPlugin` instance.** Built in `create_app`, threaded into
  `build_container` via `channels_plugin=`. Litestar transport (SSE) and
  the typed event bus must share one backend.
- **Cookie auth contract.** `ADMIN_COOKIE_NAME` is the single source of
  truth in `auth/config.py`. Cookie is `HttpOnly`, `SameSite=Strict`,
  `Secure` only when the request was HTTPS.
- **yoyo migration table per context.** `_yoyo_admin_log` is centralized
  in `admin/log/config.py::YOYO_MIGRATION_TABLE`. New contexts using the
  same DB pick a unique table name.
- **Errors propagate; adapters catch.** Domain/app code never catches
  `LayerError` to "convert" it. The global exception handler does.
- **No emoji or filler in logs.** Event names are stable literals; dynamic
  values go in kwargs (`log.info("user paid", user_id=x)`).
- **Static config in code, not env, when it doesn't vary per deployment.**
  Things like CSP defaults live in `RootConfig` with override-by-env, not
  required-by-env.

---

## 8. How-to recipes

### Add a bounded context

1. `src/<name>/{domain,app,ports/{driving,driven},adapters/{driving,driven}}/`
   with `__init__.py` re-exporting the public API via `__all__`.
2. `<name>/config.py` — Pydantic Settings, unique `env_prefix`.
3. `<name>/provider.py` — Dishka `Provider`, `Scope.APP`, maps concretes to
   `app/interfaces/` Protocols.
4. Register the provider in `src/root/composition/container.py`.
5. Register controllers (and middleware/lifespan if needed) in
   `src/root/entrypoints/api.py::create_app`.
6. Mirror tests under `tests/{unit,flow,integration,e2e}/<name>/`.

### Add a migration

1. Create `migrations/<context>/NNNN_<snake_name>.sql` (next sequential
   number; never edit applied files).
2. Migration runs at lifespan start via the context's `LifespanManager`.
3. Rollback (optional) via yoyo `-- !rollback:` block in the same file.

See [infra/yoyo.md](infra/yoyo.md).

### Add an ADR

1. Copy `docs/adr/template.md` to `docs/adr/NNNN-<decision>.md` with the
   next number.
2. ≤40 lines. One decision per file. Status: `accepted`. Date today.
3. Never renumber. Supersede with a new ADR — keep the old one in tree.

### Add a public-API symbol

If the contract isn't visible from name+types (invariants, side effects,
lifecycle constraints, failure modes), write a docstring per
[~/.claude/rules/common/documentation.md §6](../../.claude/rules/common/documentation.md).
Otherwise, no docstring.

---

## 9. Testing

Tests mirror `src/` exactly. Pyramid:

| Layer | Folder | Speed | Mocks? | Real I/O? |
|:---|:---|:---|:---|:---|
| Unit | `tests/unit/` | instant | forbidden | no |
| Flow | `tests/flow/` | fast | AsyncMock interfaces | no |
| Integration | `tests/integration/` | slow | no | yes (tmp SQLite) |
| E2E | `tests/e2e/` | slowest | no | full app via `AsyncTestClient` |

Conventions:
- Test path = `src/` path. One file per subject.
- Class names: `Test<Subject><Scenario>`. Method names: `test_<what_happens>`.
- Docstring: Given / When / Then. Body: Arrange / Act / Assert.
- E2E suite warms DI eagerly before env-isolation autouse fixtures kick in.

```bash
uv run pytest                     # full suite
uv run pytest tests/unit/         # domain only
uv run pytest tests/integration/  # SQLite repos against tmp_path
```

---

## 10. Writing docs

This project's documentation rules live in
[~/.claude/rules/common/documentation.md](../../.claude/rules/common/documentation.md).
That file defines the seven kinds of writing, line budgets, anti-patterns,
docstring/comment policy, and the MADR template.

Project-specific overrides:

- **Layout is fixed**: `docs/{contexts,subsystems,infra,adr}/`. Do not add
  new top-level folders. If something doesn't fit, it probably belongs
  inline in `architecture.md` or as an ADR.
- **One page per technology** in `docs/infra/`. New tech in the stack →
  new `infra/<tool>.md`. Don't duplicate vendor docs; link them.
- **Voice**: terse, declarative, no marketing words. Match the existing
  pages.

When you change behaviour: the doc page lands in the same PR. A stale fact
is a bug.

---

## 11. Pointers

- Per-context detail: [contexts/](contexts/)
- Cross-cutting subsystems: [subsystems/](subsystems/)
- Infra/tool reference: [infra/](infra/)
- Decisions: [adr/](adr/)
- Project-side rules: `~/.claude/rules/s-ddd_python/`
- Universal doc rules: `~/.claude/rules/common/documentation.md`
