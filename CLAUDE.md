# CLAUDE.md

Agent-specific guidance for working in this repo. Architectural facts live
in [docs/architecture.md](docs/architecture.md); this file is for things an
agent needs that a contributor wouldn't.

## Where to read first

- [docs/architecture.md](docs/architecture.md) — contexts, layers, error
  hierarchy, DI, lifespan, invariants. Start here.
- [docs/adr/](docs/adr/) — *why* the major choices were made.
- `~/.claude/rules/s-ddd_python/` — the project's S-DDD ruleset (apply it;
  do not relax).
- `~/.claude/rules/common/documentation.md` — universal docs / docstring /
  comment policy this repo follows.

## What this is

Litestar 2.23+ starter template, strict-DDD per bounded context, Dishka DI,
a file-tail admin log viewer (reads the rotating JSONL file the app
writes), role-based auth, and a Prometheus metrics endpoint via
`prometheus_client` multiprocess mode. Python 3.12+, managed with `uv`.
Logs go to stdout and to `LOG_FILE_PATH`; the admin UI tails that file.

The repo is a 2-service monorepo -- `src/litestar_backend/` (this app) and
`src/event_microservice/` (FastStream+SAQ worker, slice 2). They share only
the `video_uploaded` Valkey-Stream contract.

Two always-on example contexts ship in the template:
- `media_example/` — the golden context: plain SQLAlchemy 2.0, transactional
  outbox + relay draining to a Valkey Stream, Litestar SSE feed, full S-DDD
  layering and test pyramid. See [docs/litestar_backend/contexts/media_example.md](docs/litestar_backend/contexts/media_example.md).
- `db_example_litestar/` — SQLAlchemy 2.0 + advanced-alchemy 1.11 on Postgres,
  hybrid layering, `SQLAlchemyDTO`, `create_all`. The **only** advanced-alchemy
  user. See [docs/litestar_backend/contexts/db_example_litestar.md](docs/litestar_backend/contexts/db_example_litestar.md).

## Quick verifications

Canonical (Docker Compose — `tester` stage layers the `dev` group + `tests/`
onto the app's uv venv; full gate = `ruff check . && mypy && pytest -q`):

```bash
docker compose run --rm litestar_backend_test                       # full gate
docker compose run --rm litestar_backend_test pytest tests/unit -q  # any subset
```

Local `uv` for the fast inner loop. Integration + e2e need a Postgres
testcontainer, so **Docker must be running** (or point at an external DB via
`POSTGRES_HOST` + the other `POSTGRES_*` vars). Run from `src/litestar_backend/`
(the backend service root):

```bash
uv run pytest                     # full suite (needs Docker)
uv run pytest tests/unit/         # domain only, instant, no DB
uv run pytest tests/flow/         # app-level with mocked interfaces, no DB
uv run pytest tests/integration/  # FileLogReader (tmp_path) + real Postgres (testcontainer)
uv run pytest tests/e2e/          # full app via AsyncTestClient + Postgres
uv run ruff check . && uv run mypy
```

Test layout mirrors `src/`. Don't mix layers in one file. The `litestar_backend_test` service
is profile-gated (`profiles: ["test"]`) so `docker compose up` never starts it.
The `tester`/runtime images both copy `static/` (Jinja templates + assets);
without it the app 500s on every rendered page.

**Dev is container-only.** `docker compose up` auto-merges
`docker-compose.override.yml`, which bind-mounts host source over the image's
copy — code changes need no rebuild and no host venv is ever created (the venv
lives in the image at `/app/.venv`). Local `uv run` for the fast inner loop is
optional; its `.venv`/`.egg-info`/`__pycache__` are gitignored. Production
deploys ignore the override: `docker compose -f docker-compose.yml up`.

## Conventions worth remembering

- **msgspec** for dataclass-shaped wire payloads. Don't reach for `json`
  or manual `to_dict`. See `feedback_msgspec_preference.md` in memory.
  Pydantic only at HTTP boundaries; orjson for the structlog pipeline.
- **No env vars in business logic.** Config flows through Pydantic
  Settings → Dishka providers. Each context owns a `config.py` with a
  unique `env_prefix`.
- **Single source of truth for shared literals.** `ADMIN_COOKIE_NAME` in
  `auth/config.py`. Re-import; never duplicate.
- **No emoji.** Code, docs, log events. Pure signal.
- **Import providers/facades from the context root.** Every
  `<context>/__init__.py` re-exports its facade(s), `Config`, and `Provider`
  via `__all__`. External consumers (`root/composition/container.py`, ACLs,
  parent orchestration) write `from media_example import MediaInfraProvider` —
  never `from media_example.provider`. Submodules still use relative imports.
  Rule §2.3 in `~/.claude/rules/s-ddd_python/structure.md`.
- **Interfaces carry the contract; implementations stay bare.** Every Protocol
  method in `app/interfaces/` and every facade method gets a substantial
  docstring (behaviour, invariants, side-effects, raises). This inverts the
  global "no docstring by default" rule — the contract lives on the Protocol,
  not duplicated on each `ports/driven/` implementor. Rules: `app.md` §5,
  `ports.md` §1.
- **HTML via Jinja, assets under `static/`.** Controllers return
  `Template(template_name="<context>/<file>.html", context={...})`. All
  templates and browser assets live in the project-root `static/` folder
  that mirrors the context tree. Single Litestar mount `/static/...`;
  single `TemplateConfig(directory="static", engine=JinjaTemplateEngine)`.
  Rule §1.3 in `~/.claude/rules/s-ddd_python/structure.md`; see
  [docs/litestar_backend/infra/jinja.md](docs/litestar_backend/infra/jinja.md).
- **Migrations live in `migrations/<context>/`.** The project-root
  `migrations/` folder mirrors `src/`, `static/`, `docs/`, `tests/`. Each
  context that uses yoyo gets its own subfolder (e.g.
  `migrations/media/`), applied by the shared
  `shared/adapters/driven/postgres/run_migrations` in that context's lifespan;
  yoyo targets Postgres via the psycopg3 sync backend
  (`yoyo_url` = `postgresql+psycopg://...`). `db_example_litestar`
  uses `create_all` and has no migration files. See
  [docs/litestar_backend/infra/postgres.md](docs/litestar_backend/infra/postgres.md).
- **Both DB contexts run on SQLAlchemy** (`postgresql+asyncpg`).
  `media_example` uses plain SQLAlchemy 2.0; `db_example_litestar` is the only
  advanced-alchemy user. The shared engine/session builder lives in
  `shared/adapters/driven/postgres/`. Litestar >= 2.23.0 is required because
  advanced-alchemy 1.11 needs `litestar.di.NamedDependency`.

## Gotchas the agent will trip on

- **Single process writer.** structlog writes stdout + `LOG_FILE_PATH`; the
  admin log UI reads that file. `APP_WORKERS` is a free knob.
- **Log filters are client-side.** Level + substring filtering happen in
  the browser over loaded rows; "load more" pulls deeper into the file.
- **APP-scope DI is lazy.** The first HTTP request resolves the graph.
  Tests using env-isolation autouse fixtures must warm DI eagerly first
  — see `tests/e2e/conftest.py::e2e_client`.
- **`.env` is gitignored.** `.env.example` is the contract.
- **Test env isolation.** `tests/conftest.py::_isolate_environment` is
  autouse and deletes APP_NAME et al. before every test. Module-scoped
  fixtures must set env BEFORE that and warm DI.
- **Metrics are multi-worker safe via multiprocess mode.** The master sets
  `PROMETHEUS_MULTIPROC_DIR` and wipes stale shards before `uvicorn.run`.
  Each worker writes mmap shards; `MultiProcessCollector` merges on scrape.
  `APP_WORKERS` scales freely. `/metrics` lives in `shared` and is always on
  (no metrics context, no metrics UI). Custom metrics are module-level
  `prometheus_client` constants in the owning adapter (e.g. `videos_uploaded_total`
  in `media_example`); registered once on import, they survive repeated
  `create_app()` in tests without a duplicate-registration error. Details:
  [docs/litestar_backend/subsystems/metrics.md](docs/litestar_backend/subsystems/metrics.md).

## Editing rules

- **Docs land in the same change as the code.** Behaviour change → matching
  page in `docs/` updated. A stale fact in docs is a bug.
- **Docstrings only when the contract isn't visible from name+types.**
  Inline comments only when the WHY is non-obvious. See
  `~/.claude/rules/common/documentation.md` §6.
- **One ADR per decision, ≤40 lines, never renumber.** Supersede with a
  new ADR; keep the old one in the tree.

## Common operations

### Run locally

```bash
uv sync
cp .env.example .env
openssl rand -hex 32              # paste into AUTH_ADMIN_TOKEN

uv run start_litestar             # API workers
```

### Docker

```bash
docker compose up --build         # db (postgres:18) + app:8000; app data on /data, db on pg_data
```

### Adding a bounded context

See [docs/architecture.md §8](docs/architecture.md#8-how-to-recipes).
