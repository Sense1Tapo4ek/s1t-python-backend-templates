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
| `shared` | `src/shared/` | Cross-cutting kernel: domain types (`Role`, `Principal`), base config, error hierarchy, db connection, middleware, structlog setup. Imported by every other context; imports nothing from them. |
| `root` | `src/root/` | Entrypoints (`api.py`, `cli.py`) and DI container assembly. The only place that wires providers together. |
| `auth` | `src/auth/` | Bearer/cookie auth: token resolution, `AuthMiddleware`, `require_role` guards. See [contexts/auth.md](contexts/auth.md). |
| `admin` | `src/admin/` | Admin dashboard skeleton: login UI, dashboard shell, build-info panel. See [contexts/admin.md](contexts/admin.md). |
| `admin/log` | `src/admin/log/` | Sub-context: file-tail log viewer over the rotating JSONL file the app writes; SSE live tail, NDJSON/CSV export. See [contexts/admin-log.md](contexts/admin-log.md). |
| `metrics` | `src/metrics/` | Example infra context: Prometheus `/metrics` endpoint via multiprocess mode, plus a generic by-name custom-metrics facade. See [contexts/metrics.md](contexts/metrics.md). |

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
│   ├── driven/          # DB engines, broker clients, workers, file sources.
│   ├── middleware/      # Context-owned ASGI middleware.
│   └── lifespan/        # Optional lifespan managers (e.g. metrics sampler).
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
via the `exception_handlers` dict. Specialised handlers
(`NotAuthorizedException`, `PermissionDeniedException`, `ValidationException`)
sit ahead of the generic ones — registration order matters because Litestar
resolves the most specific handler.

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
    SharedProvider(),
    AdminProvider(),
    AdminLogWebProvider(),
    MetricsProvider(),
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
3. `build_container()` — providers wired.
4. `configure_structlog()` — JSON logger with two stdlib handlers: a
   `StreamHandler` (stdout) and a `WatchedFileHandler(LOG_FILE_PATH)`. No
   queue, no async sink.
5. `app.state.auth_facade = await container.get(AuthFacade)` — middleware-
   bound singletons resolved once.
6. `MetricsLifespanManager.start()` — ensures `multiproc_dir` exists.

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
| `admin/log/config.py::AdminLogConfig` | `LOG_` | `file_path`, `tail_lines`, `load_more_lines`, `follow_poll_ms`, `max_line_bytes`. |
| `metrics/config.py::MetricsConfig` | `METRICS_` | Prometheus endpoint path + public flag, HTTP buckets, multiproc dir. |

Rules:
- Business logic never reads `os.environ`. Config flows through providers.
- Each `env_prefix` is unique across the project.
- `RootConfig._validate_prod_invariants` enforces `AUTH_ADMIN_TOKEN`
  non-empty in `APP_ENV=prod`.

The contract for environment variables is `.env.example`. Don't commit
`.env`.

---

## 6a. Browser-served assets

Templates (Jinja2), CSS, and JS live in **one** project-root folder:

```
static/
├── shared/_base.html          # layout — every page extends this
├── admin/dashboard.html
├── admin/login.html
├── admin/forbidden.html
└── admin/log/{index.html, style.css, tail.js}
```

The folder mirrors the bounded-context tree. One Litestar mount
`/static/...` serves the directory; one `TemplateConfig(directory="static",
engine=JinjaTemplateEngine)` resolves templates. Controllers return
`Template(template_name="<context>/<file>.html", context={...})`. The
convention is captured as rule §1.3 in
`~/.claude/rules/s-ddd_python/structure.md`; the *why* is in
[adr/0008-jinja-server-side-rendering.md](adr/0008-jinja-server-side-rendering.md);
the *how* is in [infra/jinja.md](infra/jinja.md).

---

## 7. Invariants

Things that, if you change them, will break the app silently or in
production.

- **One JSONL file, two handlers.** structlog writes each record to stdout
  and to `WatchedFileHandler(LOG_FILE_PATH)`. The admin log UI reads that
  file (`tail -N`, follow, reverse-scroll). No DB, no queue, no second
  process. `APP_WORKERS` is a free knob.
- **Log filters are client-side.** Level + substring filtering happen in the
  browser over loaded rows; "load more" pulls deeper into the file.
- **Cross-worker metrics use multiprocess mode.** `prometheus_client` writes
  mmap shards to `PROMETHEUS_MULTIPROC_DIR`; no external store required.
- **Cross-context calls go through an ACL.** `db_example_sddd -> metrics` is
  the worked example: `db_example_sddd` emits a create counter + histogram via
  `ports/driven/acl/metrics_acl.py` (the only cross-context import), adapting
  `metrics.ports.driving.MetricsFacade` to its own `app/i_metrics.py` protocol.
- **APP-scope DI is lazy.** The graph resolves on the first HTTP request.
  Tests must warm DI before any global env-isolation fixture runs (see
  `tests/e2e/conftest.py::e2e_client`).
- **Cookie auth contract.** `ADMIN_COOKIE_NAME` is the single source of
  truth in `auth/config.py`. Cookie is `HttpOnly`, `SameSite=Strict`,
  `Secure` only when the request was HTTPS.
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

No context currently ships SQL migrations. If you add a SQL-backed context,
introduce a migration tool then and document it in `docs/infra/`.

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
| Integration | `tests/integration/` | slow | no | yes (tmp_path files) |
| E2E | `tests/e2e/` | slowest | no | full app via `AsyncTestClient` |

Conventions:
- Test path = `src/` path. One file per subject.
- Class names: `Test<Subject><Scenario>`. Method names: `test_<what_happens>`.
- Docstring: Given / When / Then. Body: Arrange / Act / Assert.
- E2E suite warms DI eagerly before env-isolation autouse fixtures kick in.

```bash
uv run pytest                     # full suite
uv run pytest tests/unit/         # domain only
uv run pytest tests/integration/  # ports/adapters against tmp_path files
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
