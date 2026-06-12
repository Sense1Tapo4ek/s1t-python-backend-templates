# Architecture

The decisions and invariants of this project. Read this before adding a
context or changing a layer. Audience: contributors.

For first-run / install instructions, see [README.md](../README.md).

---

## Repository shape: two independent services

This repo is a 2-service monorepo. The services share **no code** -- only two
Valkey-Stream wire contracts: `video_uploaded` (forward path) and
`video_status` (return path).

| Service | Path | Role |
|:--|:--|:--|
| `litestar_backend` | `src/litestar_backend/` | Litestar API: media_example, auth, admin, db_example_litestar. Owns Postgres + the outbox relay that publishes `video_uploaded`. |
| `event_microservice` | `src/event_microservice/` | FastStream consumer + SAQ worker. Consumes `video_uploaded`, fans work out to SAQ jobs, joins in Valkey. No Postgres. |

Each service is a standalone uv project (own `pyproject.toml` + `uv.lock`,
src-layout, own `Dockerfile`) that could be extracted to its own repo
unchanged. `docs/architecture.md` and `docs/adr/` are common; per-service
reference pages live under `docs/litestar_backend/` and
`docs/event_microservice/`.

### Wire contract: `video_uploaded`

Valkey Stream. Producer: `litestar_backend` outbox relay. Consumer:
`event_microservice`. Fields: `event_id`, `event_type`, `payload` (JSON:
`video_id`, `source_key`, `uploaded_at`, `version`). The consumer defines its
OWN inbound schema and never imports the producer's integration-event type;
idempotency is by `event_id`.

Full field-by-field contract: [contract/video_uploaded.md](contract/video_uploaded.md).

### Wire contract: `video_status`

Valkey Stream. Producer: `event_microservice` (direct XADD, no outbox).
Consumer: `litestar_backend` media_example XREADGROUP lifespan task. Carries
three event types: `video_processing_started`, `video_processed`,
`video_processing_failed`. The consumer group is `media_example`; duplicate
deliveries are absorbed by the Video status machine's `InvalidTransition`.

Full field-by-field contract: [contract/video_status.md](contract/video_status.md).

---

## 1. Bounded contexts

Each context lives at `src/<name>/` and owns its data, errors, and public
API.

| Context | Path | Responsibility |
|:---|:---|:---|
| `shared` | `src/litestar_backend/src/shared/` | Cross-cutting kernel: domain types (`Role`, `Principal`), base config, error hierarchy, `PostgresConfig` (the three driver DSNs), middleware, structlog setup. Imported by every other context; imports nothing from them. |
| `root` | `src/litestar_backend/src/root/` | Entrypoints (`api.py`, `cli.py`) and DI container assembly. The only place that wires providers together. |
| `auth` | `src/litestar_backend/src/auth/` | Bearer/cookie auth: token resolution, `AuthMiddleware`, `require_role` guards. See [litestar_backend/contexts/auth.md](litestar_backend/contexts/auth.md). |
| `admin` | `src/litestar_backend/src/admin/` | Admin dashboard skeleton: login UI, dashboard shell, build-info panel. See [litestar_backend/contexts/admin.md](litestar_backend/contexts/admin.md). |
| `admin/log` | `src/litestar_backend/src/admin/log/` | Sub-context: file-tail log viewer over the rotating JSONL file the app writes; SSE live tail, NDJSON/CSV export. See [litestar_backend/contexts/admin-log.md](litestar_backend/contexts/admin-log.md). |
| `db_example_litestar` | `src/litestar_backend/src/db_example_litestar/` | Example context: SQLAlchemy 2.0 + advanced-alchemy, hybrid layering, `SQLAlchemyDTO`. The only advanced-alchemy user (both DB contexts run on SQLAlchemy). See [litestar_backend/contexts/db_example_litestar.md](litestar_backend/contexts/db_example_litestar.md). |
| `media_example` | `src/litestar_backend/src/media_example/` | Golden context: video ingest pipeline. `POST /videos` (202) writes a video row + outbox message in one SQLAlchemy session/tx; a lifespan background relay drains the outbox to a Valkey Stream (`video_uploaded`); a second lifespan task (XREADGROUP) consumes `video_status` and drives PENDING->PROCESSING->DONE/FAILED; `GET /videos/feed` is an SSE subscription fed by the status UCs post-commit. See [litestar_backend/contexts/media_example.md](litestar_backend/contexts/media_example.md). |

Adding a context: see §8 below.

Valkey (`valkey/valkey:8`) backs `litestar.channels` for the video feed and is
the shared transport for the event-driven pipeline; configured via `ValkeyConfig`
(`VALKEY_` prefix). The `redis.asyncio` client is retained (wire-compatible).
See [litestar_backend/infra/valkey.md](litestar_backend/infra/valkey.md).

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
│   └── lifespan/        # Optional lifespan managers (e.g. outbox relay).
├── provider.py          # Dishka Provider — the only place mapping concretes to interfaces.
└── config.py            # Pydantic Settings with a unique env_prefix.
```

The full ruleset, including import direction and validation checklists,
lives in `~/.claude/rules/s-ddd_python/`. This file is the project-level
overview; that ruleset is the source of truth.

---

## 3. Error hierarchy

Defined in `src/litestar_backend/src/shared/generics/errors.py`. Four subtypes of `LayerError`
map to HTTP status codes (DomainError → 409, AppError → 422, PortError → 503,
AdapterError → 500). Every error renders as RFC 9457 `application/problem+json`
(ADR 0018). 5xx never carries a traceback.

Full hierarchy, raise/catch contract, handler registration, snitchbot
interaction, and DEV vs PROD behaviour:
[litestar_backend/subsystems/error_hierarchy.md](litestar_backend/subsystems/error_hierarchy.md).
Wire contract: [litestar_backend/contract/errors.md](litestar_backend/contract/errors.md).

---

## 4. Composition (DI)

Dishka, scoped at `Scope.APP` for everything by default. Each context exports
one `Provider`. The root assembly lives in
`src/litestar_backend/src/root/composition/container.py::build_container`.

Rules:
- Root imports only `provider.py` from each context. Never internals.
- Concrete-to-interface mapping happens in the provider, never anywhere else.
- APP-scope graph resolves lazily on the first request — see §6.

Current provider list, scopes, and container-access patterns:
[litestar_backend/infra/dishka.md](litestar_backend/infra/dishka.md).
For the *why*, see [adr/0001-dishka-for-di.md](adr/0001-dishka-for-di.md).

---

## 5. Lifespan & startup ordering

`src/litestar_backend/src/root/composition/lifespan.py` owns process startup and shutdown,
registered from `build_app`.

Order of operations on startup:
1. `RootConfig()` — fail fast on misconfig (PROD without admin token).
2. `snitchbot.init(...)` — crash reporter armed.
3. `build_container()` — providers wired.
4. `configure_structlog()` — JSON logger, two stdlib handlers:
   `StreamHandler` (stdout) + `WatchedFileHandler(LOG_FILE_PATH)`. No queue.
5. `app.state.auth_facade = await container.get(AuthFacade)` — middleware-bound
   singletons resolved once.
6. `MetricsLifespanManager.start()` — ensures `multiproc_dir` exists.

Shutdown unwinds in reverse, each in `try/finally` so one component's failure
never blocks the rest.

---

## 6. Configuration

Pydantic Settings, one `config.py` per context, unique `env_prefix`.

| File | Prefix | Owns |
|:---|:---|:---|
| `shared/config.py::BaseAppConfig` | `APP_` | `app_name`, `app_env`, `volume_path`, `runtime_path`. |
| `root/config.py::RootConfig` | `APP_` (extends Base) | server bind/port/workers, security CSP/HSTS, prod invariants. |
| `auth/config.py::AuthConfig` | `AUTH_` | `admin_token` (`SecretStr`). |
| `admin/log/config.py::AdminLogConfig` | `LOG_` | `file_path`, `tail_lines`, `load_more_lines`, `follow_poll_ms`, `max_line_bytes`. |
| `shared/config.py::MetricsConfig` | `METRICS_` | Prometheus endpoint path + public flag, HTTP buckets, multiproc dir. |
| `shared/config.py::ValkeyConfig` | `VALKEY_` | Valkey host/port/db/password/max_connections, `url` property. |
| `media_example/config.py::MediaConfig` | `MEDIA_` | schema_name, pool_size, relay_batch, relay_idle_sleep. |

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
the *how* is in [litestar_backend/infra/jinja.md](litestar_backend/infra/jinja.md).

---

## 7. Invariants

Things that, if you change them, will break the app silently or in production.

- **One JSONL file, two handlers.** structlog writes each record to stdout
  and to `WatchedFileHandler(LOG_FILE_PATH)`. The admin log UI reads that
  file (`tail -N`, follow, reverse-scroll). No DB, no queue, no second
  process. `APP_WORKERS` is a free knob.
- **Log filters are client-side.** Level + substring filtering happen in the
  browser over loaded rows; "load more" pulls deeper into the file.
- **Cross-worker metrics use multiprocess mode.** `prometheus_client` writes
  mmap shards to `PROMETHEUS_MULTIPROC_DIR`; no external store required.
- **Cross-context calls go through an ACL.** Sibling context imports go via `ports/driven/acl/`; see the S-DDD ruleset (`~/.claude/rules/s-ddd_python/ports.md §4`).
- **APP-scope DI is lazy.** The graph resolves on the first HTTP request, so
  tests must warm DI before any env-isolation fixture runs (see
  `tests/e2e/conftest.py::e2e_client`).
- **Cookie auth contract.** `ADMIN_COOKIE_NAME` lives in `auth/config.py`.
  Cookie is `HttpOnly`, `SameSite=Strict`, `Secure` only over HTTPS.
- **Errors propagate; adapters catch.** Domain/app code never catches
  `LayerError` to "convert" it — the problem+json plugin (framework
  `HTTPException`s) and the converters in `shared/adapters/problem_details.py`
  (`LayerError` subtypes) do.
- **No emoji or filler in logs.** Event names are stable literals; dynamic
  values go in kwargs (`log.info("user paid", user_id=x)`).
- **Static config in code, not env, when it doesn't vary per deployment.**
  CSP defaults live in `RootConfig` with override-by-env, not required-by-env.

---

## 8. How-to recipes

### Add a bounded context

1. `src/<name>/{domain,app,ports/{driving,driven},adapters/{driving,driven}}/`
   with `__init__.py` re-exporting the public API via `__all__`.
2. `<name>/config.py` — Pydantic Settings, unique `env_prefix`.
3. `<name>/provider.py` — Dishka `Provider`, `Scope.APP`, maps concretes to
   `app/interfaces/` Protocols.
4. Register the provider in `src/litestar_backend/src/root/composition/container.py`.
5. Register controllers (and middleware/lifespan if needed) in
   `src/litestar_backend/src/root/composition/app.py::build_app`.
6. Mirror tests under `tests/{unit,flow,integration,e2e}/<name>/`.

### Add a migration

Postgres 18, schema-per-context via `search_path` ([litestar_backend/infra/postgres.md](litestar_backend/infra/postgres.md), [adr/0019](adr/0019-sqlite-to-postgres.md)).
`media_example` ships yoyo SQL under `migrations/media/`; `db_example_litestar` uses `create_all` -- follow whichever matches your driver.

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
That file defines the eight kinds of writing, line budgets, anti-patterns,
docstring/comment policy, and the MADR template.

Project-specific overrides:

- **Layout is fixed**: `docs/litestar_backend/{contexts,subsystems,infra}/` and `docs/adr/`. Do not add
  new top-level folders. If something doesn't fit, it probably belongs
  inline in `architecture.md` or as an ADR.
- **One page per technology** in `docs/litestar_backend/infra/`. New tech in the stack →
  new `litestar_backend/infra/<tool>.md`. Don't duplicate vendor docs; link them.
- **Voice**: terse, declarative, no marketing words. Match the existing
  pages.

When you change behaviour: the doc page lands in the same PR. A stale fact
is a bug.

---

## 11. Pointers

- Per-context detail: [litestar_backend/contexts/](litestar_backend/contexts/)
- Cross-cutting subsystems: [litestar_backend/subsystems/](litestar_backend/subsystems/)
- Infra/tool reference: [litestar_backend/infra/](litestar_backend/infra/)
- Decisions: [adr/](adr/)
- Project-side rules: `~/.claude/rules/s-ddd_python/`
- Universal doc rules: `~/.claude/rules/common/documentation.md`
