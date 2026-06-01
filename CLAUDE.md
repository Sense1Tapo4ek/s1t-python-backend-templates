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

Litestar 2.21 starter template, strict-DDD per bounded context, Dishka DI,
a file-tail admin log viewer (reads the rotating JSONL file the app
writes), role-based auth, and a Prometheus metrics endpoint via
`prometheus_client` multiprocess mode. Python 3.12+, managed with `uv`.
Logs go to stdout and to `LOG_FILE_PATH`; the admin UI tails that file.

## Quick verifications

```bash
uv run pytest                     # full suite (~10s)
uv run pytest tests/unit/         # domain only, instant
uv run pytest tests/flow/         # app-level with mocked interfaces
uv run pytest tests/integration/  # FileLogReader against tmp_path JSONL
uv run pytest tests/e2e/          # full app via AsyncTestClient
uv run ruff check . && uv run mypy
```

Test layout mirrors `src/`. Don't mix layers in one file.

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
- **HTML via Jinja, assets under `static/`.** Controllers return
  `Template(template_name="<context>/<file>.html", context={...})`. All
  templates and browser assets live in the project-root `static/` folder
  that mirrors the context tree. Single Litestar mount `/static/...`;
  single `TemplateConfig(directory="static", engine=JinjaTemplateEngine)`.
  Rule §1.3 in `~/.claude/rules/s-ddd_python/structure.md`; see
  [docs/infra/jinja.md](docs/infra/jinja.md).

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
  `APP_WORKERS` scales freely. `/metrics` always-on when the context is
  composed; no admin metrics UI. e2e modules that build their own app must
  snapshot/restore `REGISTRY` to avoid collector collisions — see
  `tests/e2e/admin/metrics/conftest.py`. Details:
  [docs/subsystems/metrics.md](docs/subsystems/metrics.md).

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
docker compose up --build         # app:8000, all on /data volume
```

### Adding a bounded context

See [docs/architecture.md §8](docs/architecture.md#8-how-to-recipes).

## Deferred work

See `TODO` for items with rationale.
