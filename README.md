# litestar-base

Production-shaped Litestar starter with strict-DDD layout, Dishka DI,
a file-tail admin log viewer, role-based auth, structured logging, and a
Prometheus metrics subsystem.

Use it as a template, not a library — fork, rename, delete what you
don't need.

---

## Requirements

- Python ≥ 3.12
- [`uv`](https://docs.astral.sh/uv/) for dependency / virtualenv management

Optional Telegram credentials for crash reporting via snitchbot.

---

## First run

```bash
# 1. Sync dependencies (creates .venv automatically)
uv sync

# 2. Copy env template and fill what you need
cp .env.example .env

# 3. Generate an admin token and put it in .env (AUTH_ADMIN_TOKEN=...)
openssl rand -hex 32

# 4. Start in foreground
uv run start_litestar
```

App listens on `http://127.0.0.1:8000` (override via `APP_HOST` /
`APP_PORT`). Logs are written to `${VOLUME_PATH}/logs/app.jsonl` and to
stdout; the admin UI tails that file.


### First login

1. Open `http://127.0.0.1:8000/admin/login`.
2. Paste your `AUTH_ADMIN_TOKEN` value.
3. Cookie is set (HttpOnly, SameSite=Strict). You land on `/admin`.

In dev with `AUTH_ADMIN_TOKEN=` empty, auth is disabled and a warning
is logged at startup. `APP_ENV=prod` rejects an empty token at boot.

### Background mode

```bash
uv run start_litestar --nohup    # daemonize, tail the log
uv run start_litestar --stop     # stop the daemon (uses pidfile)
```

`RUNTIME_PATH` controls where the pidfile lives (defaults to
`/tmp/<APP_NAME>`).

---

## Project layout

Strict-DDD per-context. Top level:

```
src/
├── shared/               Cross-cutting: domain kernel, DI provider, middleware,
│                         base config
├── root/                 Entrypoints (api, cli) + container assembly
├── auth/                 Bounded context: token validation, role guard, middleware
├── admin/                Bounded context: dashboard + observability
│   ├── log/              Sub-context: file-tail log viewer (JSONL), SSE, export
│   └── metrics/          Sub-context: Prometheus `/metrics` endpoint
├── db_example_sddd/           Example context: raw aiosqlite, pool vs per-request DI
└── db_example_litestar/   Example context: SQLAlchemy + advanced-alchemy (only SQLAlchemy user)
```

Each context has its own `domain/`, `app/`, `ports/{driving,driven}/`,
`adapters/{driving,driven}/`, `provider.py`, `config.py`. See
[docs/architecture.md](docs/architecture.md) for the project's layers,
error hierarchy, DI wiring, and invariants.

---

## Tests

Canonical path is Docker Compose — same toolchain as the app image, no local
setup:

```bash
docker compose run --rm test                       # full gate: ruff + mypy + pytest
docker compose run --rm test pytest tests/unit -q  # any pytest subset
```

Local `uv` works too for the inner loop:

```bash
uv run pytest                    # full suite (~10s)
uv run pytest -q                 # quiet
uv run pytest --cov=src          # with coverage
```

Layered the same way as `src/`:

- `tests/unit/` — domain, no I/O, no mocks
- `tests/flow/` — app-level use cases with AsyncMock interfaces
- `tests/integration/` — real file system (tmp_path JSONL)
- `tests/e2e/` — full app via `AsyncTestClient`

---

## Documentation

Start at [docs/architecture.md](docs/architecture.md) — the project's
decisions, layers, invariants, and how-to recipes.

| Section | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Project overview: contexts, layers, error hierarchy, DI, lifespan, invariants. |
| [docs/contexts/](docs/contexts/) | Per-bounded-context references (auth, admin, admin/log, metrics, db_example_sddd, db_example_litestar). |
| [docs/subsystems/](docs/subsystems/) | Cross-cutting: error hierarchy, observability, metrics. |
| [docs/infra/](docs/infra/) | Per-technology references (dishka, structlog, jinja, openapi). |
| [docs/adr/](docs/adr/) | Architecture Decision Records (MADR format). |

---

## Health & build info

```bash
curl http://127.0.0.1:8000/health
```

Returns app name, started_at, commit_sha, branch, dirty flag. In dev
with a checked-out repo these resolve via `git` subprocess; in
Docker/CI populate `GIT_COMMIT_SHA` / `GIT_BRANCH` / `GIT_DIRTY` env
vars (see `.env.example`).

---

## What's wired in

- **Litestar 2.23.x** — ASGI app, exception handlers, lifespan. Minimum 2.23.0 (advanced-alchemy 1.11 dependency).
- **Dishka** — DI container, APP scope.
- **structlog** — JSON logging to stdout + a rotating JSONL file.
- **msgspec** — wire-format encode/decode for events.
- **prometheus_client + Litestar `/metrics`** — per-worker counters aggregated
  via `prometheus_client` multiprocess mode (mmap shards, no external store).
  `/metrics` always on when the context is composed. See
  [docs/subsystems/metrics.md](docs/subsystems/metrics.md).
- **snitchbot** — optional Telegram crash reporter (disabled by default).

---

## Configuration reference

All vars in `.env.example`. Highlights:

- `APP_ENV` — `dev` or `prod` (lowercase). `prod` enforces non-empty `AUTH_ADMIN_TOKEN`.
- `APP_WORKERS` — number of async workers (default `1`; a free knob, single-process logging).
- `VOLUME_PATH` — persistent data root (log file, future state).
- `LOG_*` — see [contexts/admin-log.md](docs/contexts/admin-log.md#configuration).
- `METRICS_*` — see [contexts/metrics.md](docs/contexts/metrics.md#public-surface).
- `DB_EXAMPLE_SDDD_*` — see [contexts/db_example_sddd.md](docs/contexts/db_example_sddd.md#config).
- `DB_EXAMPLE_LITESTAR_*` — see [contexts/db_example_litestar.md](docs/contexts/db_example_litestar.md#config).

---

## License

(unset — choose a license before publishing)
