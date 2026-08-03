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
unchanged. Root `docs/` holds only platform + cross-service pages
(`architecture.md`, `contract/`, `infra/`, project-scope `adr/`); per-service
reference pages live under `src/litestar_backend/docs/` and
`src/event_microservice/docs/`.

### Wire contracts

Two Valkey Streams connect the services. `video_uploaded` (forward):
`litestar_backend`'s outbox relay publishes upload events; the
`event_microservice` consumer defines its OWN inbound schema and never
imports the producer's integration-event type. `video_status` (return):
`event_microservice` publishes processing-status events (direct XADD, no
outbox); a `media_example` lifespan task consumes them and drives the video
status machine. All field names, event types, group names, and delivery
guarantees live ONLY in the contract pages:
[contract/video_uploaded.md](contract/video_uploaded.md),
[contract/video_status.md](contract/video_status.md). End-to-end map:
[features/video-pipeline.md](features/video-pipeline.md).

---

## 1. Bounded contexts

Each context lives at `src/<name>/` and owns its data, errors, and public
API.

| Context | Path | Responsibility |
|:---|:---|:---|
| `shared` | `src/litestar_backend/src/shared/` | Cross-cutting kernel: domain types (`Role`, `Principal`), base config, error hierarchy, `PostgresConfig` (the three driver DSNs), middleware, structlog setup. Imported by every other context; imports nothing from them. |
| `root` | `src/litestar_backend/src/root/` | Entrypoints (`api.py`, `cli.py`) and DI container assembly. The only place that wires providers together. |
| `auth` | `src/litestar_backend/src/auth/` | Auth: registered users (argon2id, DB roles) + three credential families (JWT, API-key, static admin token) resolved by a composite chain behind `AuthMiddleware`, plus `require_role` guards. Owns the `auth` Postgres schema (`users`, `api_keys`, outbox) migrated on startup. See [litestar_backend/docs/contexts/auth.md](../src/litestar_backend/docs/contexts/auth.md), [subsystems/jwt-auth.md](../src/litestar_backend/docs/subsystems/jwt-auth.md). |
| `admin` | `src/litestar_backend/src/admin/` | Admin dashboard skeleton: login UI, dashboard shell, build-info panel. See [litestar_backend/docs/contexts/admin.md](../src/litestar_backend/docs/contexts/admin.md). |
| `admin/log` | `src/litestar_backend/src/admin/log/` | Sub-context: file-tail log viewer over the rotating JSONL file the app writes; SSE live tail, NDJSON/CSV export. See [litestar_backend/docs/contexts/admin-log.md](../src/litestar_backend/docs/contexts/admin-log.md). |
| `db_example_litestar` | `src/litestar_backend/src/db_example_litestar/` | Example context: SQLAlchemy 2.0 + advanced-alchemy, hybrid layering, `SQLAlchemyDTO`. The only advanced-alchemy user (both DB contexts run on SQLAlchemy). See [litestar_backend/docs/contexts/db_example_litestar.md](../src/litestar_backend/docs/contexts/db_example_litestar.md). |
| `media_example` | `src/litestar_backend/src/media_example/` | Golden context: video ingest pipeline. `POST /videos` (202) writes a video row + outbox message in one SQLAlchemy session/tx; a lifespan background relay drains the outbox to a Valkey Stream (`video_uploaded`); a second lifespan task (XREADGROUP) consumes `video_status` and drives PENDING->PROCESSING->DONE/FAILED; `GET /videos/feed` is an SSE subscription fed by the status UCs post-commit. See [litestar_backend/docs/contexts/media_example.md](../src/litestar_backend/docs/contexts/media_example.md). |

Adding a context: see §8 below.

Valkey (`valkey/valkey:8`) backs `litestar.channels` for the video feed and is
the shared transport for the event-driven pipeline; configured via `ValkeyConfig`
(`VALKEY_` prefix). The `redis.asyncio` client is retained (wire-compatible).
See [infra/valkey.md](infra/valkey.md).

---

## 2. Layers (S-DDD)

Every context has the same four layers -- `domain/`, `app/`, `ports/`,
`adapters/`. `ports/` and `adapters/` each split into a driving and a driven
**side**; a side is not a layer, it is which direction the call flows. Rules
are non-negotiable; relaxing them is what kills the template's ability to grow.

```
<context>/
├── domain/              # Pure stdlib. Aggregates, VOs, domain events, domain errors.
├── app/                 # Use cases. Orchestration only -- no I/O, no frameworks.
│   └── interfaces/      # Protocol definitions for every driven port.
├── ports/
│   ├── driving/         # Facades + Pydantic schemas (the public API).
│   └── driven/          # Repos, gateways, ACLs (implement app/interfaces).
├── adapters/
│   ├── driving/         # Controllers, consumers, CLI commands.
│   ├── driven/          # DB engines, broker clients, workers, file sources.
│   ├── middleware/      # Context-owned ASGI middleware.
│   └── lifespan/        # Optional lifespan managers (e.g. outbox relay).
├── provider.py          # Dishka Provider -- the only place mapping concretes to interfaces.
└── config.py            # Pydantic Settings with a unique env_prefix.
```

---

## 3. Error hierarchy

Defined in `src/litestar_backend/src/shared/generics/errors.py`. Subtypes of
`LayerError` map to HTTP status codes: DomainError -> 409, AppError -> 422,
NotFoundError (nested under AppError, so 404 wins by MRO) -> 404,
PortError -> 503.
A truly unexpected failure renders a generic 500 via the PROD catch-all
(`unexpected_to_problem`). Every error renders as RFC 9457 `application/problem+json`
(ADR 0018). 5xx never carries a traceback. (The canonical ruleset's `AdapterError`
is deliberately omitted -- no honest raise-site; see the error-hierarchy subsystem doc.)

Full hierarchy, raise/catch contract, handler registration, snitchbot
interaction, and DEV vs PROD behaviour:
[litestar_backend/docs/subsystems/error_hierarchy.md](../src/litestar_backend/docs/subsystems/error_hierarchy.md).
Wire contract: [contract/common.md](contract/common.md).

---

## 4. Composition (DI)

Dishka, scoped at `Scope.APP` for everything by default. Each context exports
one `Provider`. The root assembly lives in
`src/litestar_backend/src/root/composition/container.py::build_container`.

Rules:
- Root imports only `provider.py` from each context. Never internals.
- Concrete-to-interface mapping happens in the provider, never anywhere else.
- APP-scope graph resolves lazily on the first request -- see §6.

Current provider list, scopes, and container-access patterns:
[litestar_backend/docs/infra/dishka.md](../src/litestar_backend/docs/infra/dishka.md).
For the *why*, see [adr/0001-dishka-for-di.md](adr/0001-dishka-for-di.md).

---

## 5. Lifespan & startup ordering

`src/litestar_backend/src/root/composition/lifespan.py` owns process startup and shutdown,
registered from `build_app`.

Order of operations on startup:
1. `RootConfig()` -- fail fast on misconfig (PROD without admin token).
2. `snitchbot.init(...)` -- crash reporter armed.
3. `build_container(channels=...)` -- providers wired; the `ChannelsPlugin`
   instance enters the container as Dishka context.
4. `configure_structlog()` -- JSON logger, two stdlib handlers:
   `StreamHandler` (stdout) + `WatchedFileHandler(LOG_FILE_PATH)`. No queue.
5. `app.state.auth_facade = await container.get(AuthFacade)` -- middleware-bound
   singletons resolved once.
6. `AuthLifespanManager.start()` -- runs the `auth` schema migration
   (`api_keys` table). First of the three managers.
7. `DbExampleLitestarLifespanManager.start()` -- `create_all` for the
   advanced-alchemy example.
8. `MediaLifespanManager.start()` -- media migrations, then two background
   tasks: the outbox relay and the `video_status` consumer.

Shutdown unwinds in reverse, each in `try/finally` so one component's failure
never blocks the rest.

---

## 6. Configuration

Pydantic Settings, one `config.py` per context, unique `env_prefix`.

| File | Prefix | Owns |
|:---|:---|:---|
| `shared/config.py::BaseAppConfig` | `APP_` | `app_name`, `app_env`, `volume_path`, `runtime_path`. |
| `root/config.py::RootConfig` | `APP_` (extends Base) | server bind/port/workers, security CSP/HSTS, prod invariants. |
| `auth/config.py::AuthConfig` | `AUTH_` | `admin_token` (`SecretStr`), `jwt_secret`, `jwt_issuer`, `jwt_access_ttl_seconds`, `jwt_refresh_ttl_seconds`, `schema_name`, `pool_size`. |
| `admin/log/config.py::AdminLogConfig` | `LOG_` | `file_path`, `tail_lines`, `load_more_lines`, `follow_poll_ms`, `max_line_bytes`. |
| `shared/config.py::MetricsConfig` | `METRICS_` | Prometheus endpoint path + public flag, HTTP buckets, multiproc dir. |
| `shared/config.py::ValkeyConfig` | `VALKEY_` | Valkey host/port/db/password/max_connections, `url` property. |
| `shared/config.py::PostgresConfig` | `POSTGRES_` | host, port, user, password, db; exposes the asyncpg/alchemy/yoyo DSNs. |
| `media_example/config.py::MediaConfig` | `MEDIA_` | schema_name, pool_size, relay_batch, relay_idle_sleep, status_batch, status_block_ms, status_claim_idle_ms. |
| `db_example_litestar/config.py::DbExampleLitestarConfig` | `DB_EXAMPLE_LITESTAR_` | schema_name, pool_size. |

Rules:
- Business logic never reads `os.environ`. Config flows through providers.
- Each `env_prefix` is unique across the project.
- `RootConfig._validate_prod_invariants` enforces `AUTH_ADMIN_TOKEN`
  non-empty in `APP_ENV=prod`.

The contract for environment variables is `.env.full.example` (the
minimal `.env.example` is its quick-start subset). Don't commit
`.env`.

---

## 6a. Browser-served assets

Templates (Jinja2), CSS, and JS live in **one** project-root `static/` folder
that mirrors the bounded-context tree (e.g. `shared/_base.html`,
`admin/log/{index.html, style.css, tail.js}`). One Litestar mount
`/static/...` serves the directory; one `TemplateConfig(directory="static",
engine=JinjaTemplateEngine)` resolves templates. Controllers return
`Template(template_name="<context>/<file>.html", context={...})`. The *why*
is in [adr/0008-jinja-server-side-rendering.md](../src/litestar_backend/docs/adr/0008-jinja-server-side-rendering.md);
the *how* is in [litestar_backend/docs/infra/jinja.md](../src/litestar_backend/docs/infra/jinja.md).

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
- **Cross-context calls go through an ACL.** Sibling contexts never import
  each other directly; the only allowed path is an ACL in `ports/driven/acl/`
  that imports the target's `ports/driving/` facade.
- **APP-scope DI is lazy.** The graph resolves on the first HTTP request, so
  tests must warm DI before any env-isolation fixture runs (see
  `tests/conftest.py::e2e_client`).
- **Cookie auth contract.** `ADMIN_COOKIE_NAME` lives in `auth/config.py`.
  Cookie is `HttpOnly`, `SameSite=Strict`, `Secure` only over HTTPS.
- **Errors propagate; adapters catch.** Domain/app code never catches
  `LayerError` to "convert" it -- the problem+json plugin (framework
  `HTTPException`s) and the converters in `shared/adapters/problem_details.py`
  (`LayerError` subtypes) do.
- **No emoji or filler in logs.** Event names are stable literals; dynamic
  values go in kwargs (`log.info("user paid", user_id=x)`).
- **Static config in code, not env, when it doesn't vary per deployment.**
  CSP defaults live in `RootConfig` with override-by-env, not required-by-env.
- **Example surfaces ship unauthenticated on purpose.** `POST/DELETE /videos`,
  the `/videos/feed` SSE stream, and the `db_example_litestar` CRUD carry no
  guard so the template is explorable. Before any real deployment add
  `require_role(...)` guards to them (or delete the example contexts).

---

## 8. How-to recipes

### Add a bounded context

1. `src/<name>/{domain,app,ports/{driving,driven},adapters/{driving,driven}}/`
   with `__init__.py` re-exporting the public API via `__all__`.
2. `<name>/config.py` -- Pydantic Settings, unique `env_prefix`.
3. `<name>/provider.py` -- Dishka `Provider`, `Scope.APP`, maps concretes to
   `app/interfaces/` Protocols.
4. Register the provider in `src/litestar_backend/src/root/composition/container.py`.
5. Register controllers (and middleware/lifespan if needed) in
   `src/litestar_backend/src/root/composition/app.py::build_app`.
6. Mirror tests under `tests/{unit,flow,integration,e2e}/<name>/`.

### Add a migration

Postgres 18, schema-per-context via `search_path` ([infra/postgres.md](infra/postgres.md), [adr/0019](adr/0019-sqlite-to-postgres.md)).
`auth` and `media_example` ship yoyo SQL under `migrations/<context>/`; `db_example_litestar` uses `create_all` -- follow whichever matches your driver.

### Add an ADR

1. Copy `docs/adr/template.md` to `docs/adr/NNNN-<decision>.md` with the
   next number.
2. ≤40 lines. One decision per file. Status: `accepted`. Date today.
3. Never renumber. Supersede with a new ADR -- keep the old one in tree.

---

## 9. Testing

Tests group by context first, then level -- `tests/<context>/<level>/...`
mirrors `src/`. Pyramid:

| Level | Path | Speed | Mocks? | Real I/O? |
|:---|:---|:---|:---|:---|
| Unit | `tests/<context>/unit/` | instant | forbidden | no |
| Flow | `tests/<context>/flow/` | fast | AsyncMock interfaces | no |
| Integration | `tests/<context>/integration/` | slow | no | yes (tmp_path files) |
| E2E | `tests/<context>/e2e/` | slowest | no | full app via `AsyncTestClient` |

The level is a marker set from the path
(`conftest.py::pytest_collection_modifyitems`) -- select with `-m <level>`, not a
folder (nested contexts like `admin/log` have none). Naming and Given/When/Then
follow the S-DDD test rule; E2E suites warm DI eagerly before env isolation.

---

## 10. Writing docs

The global documentation discipline (one job + one audience per page, hard
line budgets, one home per fact, docstrings only for contracts invisible from
name+types, MADR ADRs <=40 lines) is the baseline. Project-specific overrides:

- **Layout is fixed**: root `docs/` = platform + cross-service only
  (`contract/`, `infra/` substrate, project-scope `adr/`); each service's
  reference lives in `src/<svc>/docs/{contexts,subsystems,infra,adr}/`. A page
  goes in the narrowest tree whose blast radius contains it. Do not add new
  top-level folders.
- **One page per technology**: platform substrate (Postgres, Valkey) ->
  `docs/infra/<tool>.md`; service-exclusive tech (Jinja, SAQ) ->
  `src/<svc>/docs/infra/<tool>.md`. Don't duplicate vendor docs; link them.
- **Voice**: terse, declarative, no marketing words. Match the existing
  pages.

When you change behaviour: the doc page lands in the same PR. A stale fact
is a bug.

---

## 11. Pointers

- Video pipeline end-to-end: [features/video-pipeline.md](features/video-pipeline.md)
- Per-context detail: [litestar_backend/docs/contexts/](../src/litestar_backend/docs/contexts/)
- Cross-cutting subsystems: [litestar_backend/docs/subsystems/](../src/litestar_backend/docs/subsystems/)
- Infra/tool reference: [litestar_backend/docs/infra/](../src/litestar_backend/docs/infra/)
- Decisions: [adr/](adr/)
