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
SQLite admin log subsystem with FTS5 search and SSE tail, role-based
auth, Litestar Channels event bus over Valkey. Python 3.12+, managed
with `uv`. Logs flow through a Valkey Stream consumed by a separate
`log-sink` process (single SQLite writer).

## Quick verifications

```bash
uv run pytest                     # full suite (~10s)
uv run pytest tests/unit/         # domain only, instant
uv run pytest tests/flow/         # app-level with mocked interfaces
uv run pytest tests/integration/  # real SQLite via tmp_path
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
  `auth/config.py`, `YOYO_MIGRATION_TABLE` in `admin/log/config.py`.
  Re-import; never duplicate.
- **No emoji.** Code, docs, log events. Pure signal.

## Gotchas the agent will trip on

- **Two processes per deployment.** `app` (Litestar workers, read-only
  to `admin_logs.db`) + `log-sink` (single writer, drains Valkey Stream
  into SQLite). `APP_WORKERS` is now a free knob — the sink is the only
  writer. Docker Compose wires both; bare `start_litestar` needs
  `start_log_sink` running alongside in another shell.
- **Valkey is required.** Both processes need it (`VALKEY_URL`). Producers
  use Streams (`LOG_STREAM_KEY`); SSE fan-out uses pub/sub
  (`LOG_EVENTS_CHANNEL`). If Valkey is down, logs buffer in-process and
  drop with throttled stderr warnings — no crash.
- **APP-scope DI is lazy.** The first HTTP request resolves the graph.
  Tests using env-isolation autouse fixtures must warm DI eagerly first
  — see `tests/e2e/conftest.py::e2e_client`.
- **Channels plugin is shared.** Built in `create_app()` with a
  `RedisChannelsPubSubBackend`, threaded through `app.state.channels_plugin`
  into `build_container()`. Litestar transport (SSE) and the typed event
  bus must hit the same backend. The backend's Redis client is closed
  manually in lifespan stop (it doesn't own it).
- **`.env` is gitignored.** `.env.example` is the contract.
- **Test env isolation.** `tests/conftest.py::_isolate_environment` is
  autouse and deletes APP_NAME et al. before every test. Module-scoped
  fixtures must set env BEFORE that and warm DI.
- **Metrics are multi-worker safe.** Per-process counters live in
  `prometheus_client.REGISTRY`. Cross-worker snapshots (RSS, loop lag,
  queue depth) flow through Valkey hashes and are merged on every scrape.
  `APP_WORKERS` can be tuned freely. `/metrics` always-on when the context
  is composed; admin UI gated by `METRICS_ENABLED`. e2e modules that build
  their own app must snapshot/restore `REGISTRY` to avoid collector
  collisions — see `tests/e2e/admin/metrics/conftest.py`. Details:
  [docs/subsystems/metrics.md](docs/subsystems/metrics.md).

## Editing rules

- **Docs land in the same change as the code.** Behaviour change → matching
  page in `docs/` updated. A stale fact in docs is a bug.
- **Docstrings only when the contract isn't visible from name+types.**
  Inline comments only when the WHY is non-obvious. See
  `~/.claude/rules/common/documentation.md` §6.
- **Never edit applied migrations.** Add a new file under
  `migrations/<context>/`. See [docs/infra/yoyo.md](docs/infra/yoyo.md).
- **One ADR per decision, ≤40 lines, never renumber.** Supersede with a
  new ADR; keep the old one in the tree.

## Common operations

### Run locally

```bash
uv sync
cp .env.example .env
openssl rand -hex 32              # paste into AUTH_ADMIN_TOKEN
docker run -d -p 6379:6379 valkey/valkey:8-alpine  # bus, or `docker compose up valkey -d`

uv run start_litestar             # API workers
uv run start_log_sink             # in a separate shell — drains Valkey -> SQLite
```

### Docker

```bash
docker compose up --build         # valkey + app:8000 + log-sink, all on /data volume
```

### Adding a bounded context

See [docs/architecture.md §8](docs/architecture.md#8-how-to-recipes).

## Deferred work

See `TODO` for items with rationale.
