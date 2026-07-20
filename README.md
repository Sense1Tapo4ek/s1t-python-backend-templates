# s1t-python-backend-templates

Production-shaped template: a two-service, event-driven monorepo.

- **`litestar_backend`** — Litestar API with strict-DDD layout, Dishka DI,
  role-based auth (JWT, API keys, static admin token), an admin UI (dashboard
  + file-tail log viewer), Prometheus metrics, and a transactional-outbox
  video pipeline.
- **`event_microservice`** — FastStream consumer + SAQ worker. Consumes the
  `video_uploaded` Valkey Stream and fans heavy work out to SAQ jobs.

The services share **no code** — only the `video_uploaded` wire contract
([docs/contract/video_uploaded.md](docs/contract/video_uploaded.md)). Each is
a standalone uv project that could be extracted to its own repo unchanged.

Use it as a template, not a library — fork, rename, delete what you don't need.

---

## Requirements

- Docker + Docker Compose (dev is container-only; source is bind-mounted, no
  host venv needed)
- [`uv`](https://docs.astral.sh/uv/) — optional, for the fast local inner loop

---

## First run

```bash
# 1. Copy env template, generate an admin token
cp .env.example .env
openssl rand -hex 32        # paste into AUTH_ADMIN_TOKEN=...

# 2. Start everything: Postgres, Valkey, API, consumer, SAQ worker
docker compose up --build
```

`docker-compose.override.yml` is auto-merged: it bind-mounts `src/` over the
image copy, so code changes need no rebuild. Production deploys ignore it:
`docker compose -f docker-compose.yml up`.

| What | URL |
|---|---|
| API | `http://localhost:8000` |
| Admin login | `http://localhost:8000/admin/login` |
| Admin dashboard + log viewer | `http://localhost:8000/admin` |
| OpenAPI UI | `http://localhost:8000/schema/swagger` (needs the dev CSP from `.env.example`) |
| Backend Prometheus metrics | `http://localhost:8000/metrics` |
| SAQ admin panel (jobs, retry/abort) | `http://localhost:8081` |
| Consumer / worker Prometheus metrics | `http://localhost:9101/metrics`, `http://localhost:9102/metrics` |

### Admin login

1. Open `/admin/login`, paste your `AUTH_ADMIN_TOKEN` value.
2. Cookie is set (HttpOnly, SameSite=Strict). You land on `/admin`.

With `AUTH_ADMIN_TOKEN=` empty, auth is disabled and a warning is logged at
startup (dev only). `APP_ENV=prod` rejects an empty token at boot.

### SAQ admin panel

The SAQ worker serves its monitoring UI (queue stats, per-job detail, retry
and abort) on host port **8081** — enabled by the `--web` flag on the
`event_microservice_worker` command. Set `SAQ_WEB_PASSWORD` in `.env` to put
it behind HTTP Basic auth (user `admin`); empty = no auth, dev only. Details:
[src/event_microservice/docs/infra/saq.md](src/event_microservice/docs/infra/saq.md).

### Try the pipeline

```bash
curl -X POST http://localhost:8000/videos \
  -H "Content-Type: application/json" \
  -d '{"source_key": "uploads/demo.mp4"}'
```

The API writes the video row + outbox message in one transaction; a relay
publishes `video_uploaded` to a Valkey Stream; the consumer enqueues three SAQ
jobs (stt, plagiarism, transcode); the worker joins their completion in
Valkey and publishes `video_status` events back; the backend consumer drives
the video through PENDING -> PROCESSING -> DONE/FAILED and broadcasts each
transition to the SSE feed at `/videos/feed`. Watch it in the SAQ panel and
the admin log viewer.

---

## Project layout

```
src/
├── litestar_backend/         Litestar API (own pyproject.toml + uv.lock + Dockerfile)
│   ├── src/
│   │   ├── shared/           Cross-cutting kernel: config, errors, Postgres/Valkey/metrics infra
│   │   ├── root/             Entrypoints + Dishka container assembly
│   │   ├── auth/             JWT + API-key + static bearer/cookie auth, role guards, middleware
│   │   ├── admin/            Admin dashboard; admin/log/ = file-tail log viewer (SSE, export)
│   │   ├── media_example/    GOLDEN CONTEXT: outbox + relay + SSE, full S-DDD layering
│   │   └── db_example_litestar/  Hybrid CRUD example: advanced-alchemy + SQLAlchemyDTO
│   ├── migrations/           yoyo migrations, one folder per context
│   ├── static/               Jinja templates + assets, mirrors the context tree
│   └── tests/                unit / flow / integration / e2e — mirrors src/
└── event_microservice/       FastStream consumer + SAQ worker (own pyproject + lock)
    ├── src/
    │   ├── shared/           Own Valkey client, logging, base errors
    │   ├── root/             Container + two entrypoints: consumer, saq_worker
    │   └── media_processing/ Bounded context: jobs, join policy, SAQ queue port
    └── tests/
```

Every context keeps the same S-DDD layers: `domain/`, `app/`,
`ports/{driving,driven}/`, `adapters/`, `provider.py`, `config.py`. Layer
rules, error hierarchy, DI and invariants:
[docs/architecture.md](docs/architecture.md).

---

## Technology map — what to use where

| Technology | Where it lives | Use it for |
|---|---|---|
| Litestar 2.23+ | `litestar_backend` adapters | HTTP controllers, SSE, guards, exception handlers |
| Dishka | `provider.py` per context, `root/composition` | All wiring; business code never builds its dependencies |
| Pydantic / pydantic-settings | `ports/driving` schemas, `config.py` | HTTP boundary validation and env config — nowhere else |
| msgspec | outbox payloads, wire events | Dataclass-shaped wire payloads (faster than json/Pydantic) |
| SQLAlchemy 2.0 (plain) | `media_example` | The default DB pattern to copy: explicit session, mappers, outbox |
| advanced-alchemy | `db_example_litestar` only | Thin CRUD where a repository/service + `SQLAlchemyDTO` suffice |
| yoyo-migrations | `migrations/<context>/` | Schema changes, applied in the context's lifespan |
| Valkey | streams, `litestar.channels`, join store | Event transport between the services; SSE fan-out; job-join state |
| FastStream | `event_microservice` consumer | Reacting to stream events (the "HTTP of the event world") |
| SAQ | `event_microservice` worker | Heavy/retryable background jobs: CPU via process pool, blocking I/O via threads |
| structlog | `shared/logging.py` in both services | Structured JSON logs; stdout + the JSONL file the admin UI tails (orjson renderer in the backend) |
| prometheus_client | `shared` (backend), worker adapters | Counters/gauges; multiprocess mode makes `APP_WORKERS` a free knob |
| Jinja | `static/` + admin controllers | Server-rendered admin pages; no SPA build step |

Picking an example to copy: start from **`media_example`** for anything with
real business logic (full layering, domain events, outbox, tests at all four
levels). Use **`db_example_litestar`** only for thin CRUD with no invariants.

---

## Tests

Canonical path is Docker Compose — same toolchain as the app images:

```bash
docker compose run --rm litestar_backend_test                       # ruff + mypy + pytest
docker compose run --rm litestar_backend_test pytest tests/unit -q  # any subset
docker compose run --rm event_microservice_test
```

Local `uv` inner loop (run from the service root, e.g. `src/litestar_backend/`):

```bash
uv run pytest tests/unit tests/flow   # instant, no DB
uv run pytest                         # full suite — needs Docker (testcontainers)
uv run ruff check . && uv run mypy
```

Test layout mirrors `src/`: `unit/` (domain, no mocks), `flow/` (use cases,
mocked interfaces), `integration/` (real Postgres/Valkey), `e2e/` (full app).

The [`Taskfile`](Taskfile.yml) wraps these (`task test`, `task be:unit`) and a
`pre-commit` gate runs ruff/mypy/gitleaks on every commit — full dev-tooling guide
in [docs/development.md](docs/development.md).

---

## Documentation

Start at [docs/architecture.md](docs/architecture.md) — decisions, layers,
invariants, how-to recipes.

| Section | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Both services: contexts, layers, error hierarchy, DI, lifespan, invariants. |
| [docs/development.md](docs/development.md) | Dev workflow: Taskfile commands, the pre-commit gate, the pinned monorepo toolchain. |
| [src/litestar_backend/docs/](src/litestar_backend/docs/index.md) | Backend references: `contexts/`, `subsystems/` (errors, observability, metrics), `infra/` (dishka, structlog, jinja, openapi), service ADRs. |
| [src/event_microservice/docs/](src/event_microservice/docs/index.md) | Worker references: `contexts/media_processing.md`, `infra/` (faststream, saq), service ADRs. |
| [docs/contract/](docs/contract/README.md) | Wire contracts: `video_uploaded`, `video_status`, the HTTP error envelope. |
| [docs/infra/](docs/infra/) | Platform substrate: Postgres, Valkey. |
| [docs/adr/](docs/adr/README.md) | Project-scope ADRs (MADR); service- and context-scope trees live with their service. |

---

## Health & build info

```bash
curl http://localhost:8000/health
```

Returns app name, started_at, commit_sha, branch, dirty flag. In dev with a
checked-out repo these resolve via `git`; in Docker/CI populate
`GIT_COMMIT_SHA` / `GIT_BRANCH` / `GIT_DIRTY` (see `.env.example`).

---

## License

[MIT](LICENSE)
