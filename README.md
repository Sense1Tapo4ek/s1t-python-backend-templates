# s1t-litestar-template

**An architecture you can read.** Two services, zero shared code, strict DDD
in every context — a production-shaped monorepo template where the patterns
are the product and the features exist to prove them.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-e3b661)](https://www.python.org/)
[![Litestar 2.24+](https://img.shields.io/badge/litestar-2.24%2B-e3b661)](https://litestar.dev/)
[![Tests](https://img.shields.io/badge/tests-364-9cc48c)](#tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-c9bda8)](LICENSE)

**[→ The landing page](https://sense1tapo4ek.github.io/s1t-python-backend-templates/)**
tells this story visually.

---

## Topology

```
┌──────────────────────┐   video_uploaded (stream)   ┌──────────────────────┐
│   litestar_backend   │ ──────────────────────────▶ │  event_microservice  │
│  HTTP · Postgres     │                             │  FastStream · SAQ    │
│  outbox · auth · SSE │ ◀────────────────────────── │  Valkey join · jobs  │
└──────────────────────┘    video_status (stream)    └──────────────────────┘
```

Only wire contracts cross the boundary — not a single shared import. Each
service is a standalone uv project (own `pyproject.toml`, lock, Dockerfile)
you could extract to its own repo unchanged. Contracts:
[docs/contract/](docs/contract/README.md).

## Anatomy of a context

Every bounded context keeps the same four layers; imports point inward only,
enforced by import-linter:

```
adapters ──▶ ports ──▶ app ──▶ domain
controllers  facades   use cases  pure stdlib
engines      repos     Protocols  aggregates, VOs, events
```

Plus `provider.py` (Dishka DI — the only wiring point) and `config.py` (own
env prefix). Siblings talk through ACLs; every decision has an ADR. Full
rules: [docs/architecture.md](docs/architecture.md).

## Pattern catalog

| Pattern | What it buys | Where |
|---|---|---|
| Transactional outbox | row + event commit atomically; relay drains to a Valkey Stream | [`shared/adapters/driven/outbox_relay.py`](src/litestar_backend/src/shared/adapters/driven/outbox_relay.py) · [ADR 0031](src/litestar_backend/docs/adr/0031-shared-generic-patterns.md) |
| Inbox dedup | at-least-once delivery, exactly-once effect via `event_id` inbox | [delivery-guarantees.md](src/event_microservice/docs/subsystems/delivery-guarantees.md) |
| Composite auth chain | JWT → API-key → static token, first match wins, fail-closed | [`auth/ports/driven/composite_token_resolver.py`](src/litestar_backend/src/auth/ports/driven/composite_token_resolver.py) · [ADR 0032](src/litestar_backend/docs/adr/0032-user-identity-model.md) |
| Keyset pagination | opaque cursors, stable pages under writes, one generic `Page[T]` | [`shared/generics/pagination.py`](src/litestar_backend/src/shared/generics/pagination.py) |
| Integration-event envelope | `event_id` + `version` + `occurred_at` on every wire event by construction | [`shared/generics/integration_event.py`](src/litestar_backend/src/shared/generics/integration_event.py) |
| Graceful drain | lifespan managers own their background tasks and stop them inside the grace window | [`media_example/adapters/lifespan_manager.py`](src/litestar_backend/src/media_example/adapters/lifespan_manager.py) |

## One request, every pattern

```bash
curl -X POST http://localhost:8000/videos \
  -H "Content-Type: application/json" \
  -d '{"source_key": "uploads/demo.mp4"}'
```

The API writes the video row + outbox message in one transaction; a relay
publishes `video_uploaded` to a Valkey Stream; the consumer enqueues three
SAQ jobs (stt, plagiarism, transcode); the worker joins their completion in
Valkey and publishes `video_status` back; the backend drives the video
through PENDING → PROCESSING → DONE/FAILED and broadcasts each transition to
the SSE feed at `/videos/feed`. Watch it in the SAQ panel and the admin log
viewer.

---

## First run

```bash
cp .env.example .env      # minimal; every knob: .env.full.example
openssl rand -hex 32      # paste into AUTH_ADMIN_TOKEN=...
docker compose up --build # Postgres, Valkey, API, consumer, SAQ worker
```

Dev is container-only: `docker-compose.override.yml` is auto-merged and
bind-mounts `src/` over the image copy, so code changes need no rebuild.
Production ignores it: `docker compose -f docker-compose.yml up`.

| What | URL |
|---|---|
| API | `http://localhost:8000` |
| Admin login → dashboard + log viewer | `http://localhost:8000/admin/login` |
| OpenAPI UI | `http://localhost:8000/schema/swagger` (needs the dev CSP from `.env.full.example`) |
| Backend Prometheus metrics | `http://localhost:8000/metrics` |
| SAQ admin panel (jobs, retry/abort) | `http://localhost:8081` |
| Consumer / worker metrics | `http://localhost:9101/metrics`, `http://localhost:9102/metrics` |

Admin auth: paste `AUTH_ADMIN_TOKEN` at `/admin/login` (HttpOnly cookie,
SameSite=Strict). Empty token disables auth with a startup warning — dev
only; `APP_ENV=prod` rejects it at boot. The SAQ panel takes
`SAQ_WEB_PASSWORD` for HTTP Basic (user `admin`); details:
[saq.md](src/event_microservice/docs/infra/saq.md).

## Project layout

```
src/
├── litestar_backend/         Litestar API (own pyproject.toml + uv.lock + Dockerfile)
│   ├── src/
│   │   ├── shared/           Cross-cutting kernel: config, errors, Postgres/Valkey/metrics infra
│   │   ├── root/             Entrypoints + Dishka container assembly
│   │   ├── auth/             Users (argon2id) + JWT + API keys + admin token, role guards
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

Picking an example to copy: start from **`media_example`** for anything with
real business logic (full layering, domain events, outbox, tests at all four
levels). Use **`db_example_litestar`** only for thin CRUD with no invariants.

## Technology map

| Technology | Where it lives | Use it for |
|---|---|---|
| Litestar 2.24+ | `litestar_backend` adapters | HTTP controllers, SSE, guards, exception handlers |
| Dishka | `provider.py` per context, `root/composition` | All wiring; business code never builds its dependencies |
| Pydantic / pydantic-settings | `ports/driving` schemas, `config.py` | HTTP boundary validation and env config — nowhere else |
| msgspec | outbox payloads, wire events | Dataclass-shaped wire payloads (faster than json/Pydantic) |
| SQLAlchemy 2.0 (plain) | `media_example` | The default DB pattern to copy: explicit session, mappers, outbox |
| advanced-alchemy | `db_example_litestar` only | Thin CRUD where a repository/service + `SQLAlchemyDTO` suffice |
| yoyo-migrations | `migrations/<context>/` | Schema changes, applied in the context's lifespan |
| Valkey | streams, `litestar.channels`, join store | Event transport between services; SSE fan-out; job-join state |
| FastStream | `event_microservice` consumer | Reacting to stream events (the "HTTP of the event world") |
| SAQ | `event_microservice` worker | Heavy/retryable jobs: CPU via process pool, blocking I/O via threads |
| structlog | `shared/logging.py` in both services | Structured JSON logs; stdout + the JSONL file the admin UI tails |
| prometheus_client | `shared` (backend), worker adapters | Counters/gauges; multiprocess mode makes `APP_WORKERS` a free knob |
| Jinja | `static/` + admin controllers | Server-rendered admin pages; no SPA build step |

## Tests

Canonical path is Docker Compose — same toolchain as the app images:

```bash
docker compose run --rm litestar_backend_test                       # ruff + mypy + pytest
docker compose run --rm litestar_backend_test pytest tests/unit -q  # any subset
docker compose run --rm event_microservice_test
```

Local `uv` inner loop (from the service root, e.g. `src/litestar_backend/`):

```bash
uv run pytest tests/unit tests/flow   # instant, no DB
uv run pytest                         # full suite — needs Docker (testcontainers)
uv run ruff check . && uv run mypy
```

Test layout mirrors `src/`: `unit/` (domain, no mocks), `flow/` (use cases,
mocked interfaces), `integration/` (real Postgres/Valkey), `e2e/` (full app).
The [`Taskfile`](Taskfile.yml) wraps these (`task test`, `task be:unit`) and
`pre-commit` runs ruff/mypy/gitleaks on every commit — see
[docs/development.md](docs/development.md).

## Documentation

| Section | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Both services: contexts, layers, error hierarchy, DI, lifespan, invariants. |
| [docs/contract/](docs/contract/README.md) | Wire contracts: `video_uploaded`, `video_status`, the HTTP error envelope. |
| [docs/adr/](docs/adr/README.md) | Project-scope ADRs (MADR); service- and context-scope trees live with their service. |
| [src/litestar_backend/docs/](src/litestar_backend/docs/index.md) | Backend: `contexts/`, `subsystems/`, `infra/`, service ADRs. |
| [src/event_microservice/docs/](src/event_microservice/docs/index.md) | Worker: `contexts/media_processing.md`, `infra/` (faststream, saq), service ADRs. |
| [docs/development.md](docs/development.md) | Dev workflow: Taskfile, pre-commit gate, pinned toolchain. |
| [docs/infra/](docs/infra/) | Platform substrate: Postgres, Valkey. |

---

A template, not a framework: fork it, rename it, delete what you don't need.

[MIT](LICENSE)
