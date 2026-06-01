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

Valkey (Redis-compatible) is required for the metrics subsystem. Optional
Telegram credentials for crash reporting via snitchbot.

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

Metrics need Valkey: `docker run -d -p 6379:6379 valkey/valkey:8-alpine`
(or `docker compose up valkey -d`).

### First login

1. Open `http://127.0.0.1:8000/admin/login`.
2. Paste your `AUTH_ADMIN_TOKEN` value.
3. Cookie is set (HttpOnly, SameSite=Strict). You land on `/admin`.

In dev with `AUTH_ADMIN_TOKEN=` empty, auth is disabled and a warning
is logged at startup. `APP_ENV=PROD` rejects an empty token at boot.

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
├── shared/          Cross-cutting: domain kernel, DI provider, middleware,
│                    event bus, db connection, base config
├── root/            Entrypoints (api, cli) + container assembly
├── auth/            Bounded context: token validation, role guard, middleware
└── admin/           Bounded context: dashboard + observability
    ├── log/         Sub-context: file-tail log viewer (JSONL), SSE, export
    └── metrics/     Sub-context: Prometheus endpoint, admin dashboard, plugin registry
```

Each context has its own `domain/`, `app/`, `ports/{driving,driven}/`,
`adapters/{driving,driven}/`, `provider.py`, `config.py`. See
[docs/architecture.md](docs/architecture.md) for the project's layers,
error hierarchy, DI wiring, and invariants.

---

## Tests

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
| [docs/contexts/](docs/contexts/) | Per-bounded-context references (auth, admin, admin/log, admin/metrics). |
| [docs/subsystems/](docs/subsystems/) | Cross-cutting: event bus, error hierarchy, observability. |
| [docs/infra/](docs/infra/) | Per-technology references (dishka, structlog, valkey, jinja). |
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

- **Litestar 2.21.x** — ASGI app, exception handlers, lifespan.
- **Dishka** — DI container, APP scope.
- **structlog** — JSON logging to stdout + a rotating JSONL file.
- **msgspec** — wire-format encode/decode for events.
- **Valkey** — shared store for cross-worker metrics snapshots. See [docs/infra/valkey.md](docs/infra/valkey.md).
- **prometheus_client + Litestar `/metrics`** — per-worker counters,
  cross-worker snapshots aggregated via Valkey, admin dashboard at
  `/admin/metrics` with a per-module plugin contract. See
  [docs/subsystems/metrics.md](docs/subsystems/metrics.md).
- **snitchbot** — optional Telegram crash reporter (disabled by default).

---

## Configuration reference

All vars in `.env.example`. Highlights:

- `APP_ENV` — `dev` or `PROD`. PROD enforces non-empty `AUTH_ADMIN_TOKEN`.
- `APP_WORKERS` — number of async workers (default `1`; a free knob, single-process logging).
- `VOLUME_PATH` — persistent data root (log file, future state).
- `LOG_*` — see [contexts/admin-log.md](docs/contexts/admin-log.md#configuration).
- `METRICS_*` — see [contexts/admin-metrics.md](docs/contexts/admin-metrics.md#public-surface).

---

## License

(unset — choose a license before publishing)
