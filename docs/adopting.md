# Adopting the template

Checklist for turning this template into your project. Audience: adopter,
first day. Do the rename first, then decide which example contexts to keep.

## 1. Rename the template

The project name appears as `litestar-base` (display/app name),
`litestar_base` (Postgres DB name), and the two service package names.
Work through:

- [ ] `.env.example` + `.env.full.example` — `APP_NAME=litestar-base`,
      `POSTGRES_DB=litestar_base`, the commented `RUNTIME_PATH` and
      `AUTH_JWT_ISSUER` values.
- [ ] `docker-compose.yml` — `POSTGRES_DB: litestar_base` (three services:
      `db`, `litestar_backend`, `litestar_backend_test`); image tags
      `litestar-backend:{local,test}`, `event-microservice:{local,test}`;
      optionally the service names themselves (`litestar_backend`,
      `litestar_backend_test`, `event_microservice`,
      `event_microservice_worker`, `event_microservice_test` — if renamed,
      update `Taskfile.yml` in the same change).
- [ ] `src/litestar_backend/pyproject.toml` — `name = "litestar_backend"`
      (and the `description`).
- [ ] `src/event_microservice/pyproject.toml` — `name = "event_microservice"`.
- [ ] Regenerate both lockfiles after the pyproject edits:
      `cd src/litestar_backend && uv lock`, `cd src/event_microservice && uv lock`.
- [ ] Code-level defaults and wire literals (they fall back when env is unset):
      `shared/config.py` (`app_name` default), `auth/config.py` (`jwt_issuer`
      default), `shared/adapters/problem_details.py`
      (`urn:litestar-base:error` problem-type base) + the example in
      `shared/adapters/openapi.py`, `root/composition/app.py`
      (`_pkg_version("litestar-base")`, OpenAPI contact), the 401/403 types in
      `admin/adapters/driving/error_handlers.py`.
- [ ] `README.md` — title (`s1t-litestar-template`) and prose references.
- [ ] Sweep for stragglers:
      `grep -rn "litestar-base\|litestar_base" --exclude-dir=.venv --exclude=uv.lock .`

## 2. Delete the example contexts

Two always-on examples ship in the backend. `media_example` is the golden
S-DDD reference; `db_example_litestar` is the advanced-alchemy CRUD sample.
Delete either or both once you have your own contexts.

### 2a. Delete `db_example_litestar`

- [ ] `src/litestar_backend/src/db_example_litestar/` — the context source.
- [ ] `src/litestar_backend/src/root/composition/container.py` — drop the
      `DbExampleLitestarProvider` import + registration.
- [ ] `src/litestar_backend/src/root/composition/lifespan.py` — drop the
      `DbExampleLitestarLifespanManager` import, `start()` and `stop()`.
- [ ] `src/litestar_backend/src/root/composition/app.py` — drop the
      `AuthorController`/`BookController` imports + route registration and
      the `db_example (Alchemy)` OpenAPI tag.
- [ ] No migrations to remove (`create_all`, no files).
- [ ] Tests: `src/litestar_backend/tests/{unit,flow,integration,e2e}/db_example_litestar/`.
- [ ] Docs: `src/litestar_backend/docs/contexts/db_example_litestar.md` and
      the ADR subtree `src/litestar_backend/docs/contexts/db_example_litestar/`;
      prune references from `docs/architecture.md` and
      `src/litestar_backend/docs/index.md`.
- [ ] Env templates: drop `DB_EXAMPLE_LITESTAR_SCHEMA_NAME` from both.
- [ ] Dependency: remove `advanced-alchemy` from
      `src/litestar_backend/pyproject.toml`, then `uv lock`.

### 2b. Delete `media_example` (takes the event pipeline with it)

Backend side:

- [ ] `src/litestar_backend/src/media_example/` — the context source.
- [ ] `container.py` — drop `MediaInfraProvider` + `MediaWebProvider`.
- [ ] `lifespan.py` — drop `MediaLifespanManager` (import, start, stop).
- [ ] `app.py` — drop `VideoController`/`VideoFeedController`, the
      `VIDEOS_CHANNEL` import and the `ChannelsPlugin` channel entry, and the
      `media` OpenAPI tag. If nothing else uses Channels, remove the plugin.
- [ ] Migrations: `src/litestar_backend/migrations/media/`.
- [ ] Tests: `src/litestar_backend/tests/{unit,flow,integration,e2e}/media_example/`.
- [ ] Docs: `src/litestar_backend/docs/contexts/media_example.md`.
- [ ] Env templates: drop the `MEDIA_*` block from `.env.full.example`.

The `event_microservice` service exists only to process `video_uploaded`;
with `media_example` gone, remove it whole:

- [ ] `src/event_microservice/` — the whole service (source, tests, docs,
      pyproject, Dockerfile).
- [ ] `docker-compose.yml` — services `event_microservice`,
      `event_microservice_worker`, `event_microservice_test`.
- [ ] `Taskfile.yml` — the `em:*` targets, `test:event`, and the `EM` var;
      trim `test` / `check` loops that iterate both services.
- [ ] Contract pages: `docs/contract/video_uploaded.md`,
      `docs/contract/video_status.md`; feature map
      `docs/features/video-pipeline.md`; prune the wire-contract section from
      `docs/architecture.md`.
- [ ] Env templates: drop the `MEDIA_PROCESSING_*` block and
      `SAQ_WEB_PASSWORD`.
- [ ] Pre-commit: remove the event_microservice ruff/mypy hooks from
      `.pre-commit-config.yaml`.

Keep the ADRs (0022, 0026, 0028, and the service ADR tree) or delete them
with the code — they are history, not live contracts, but a deleted feature
should not leave docs claiming it exists.

### Verify

- [ ] `task check` and `task test` green.
- [ ] `docker compose up --build` boots; `/health` responds.
- [ ] `grep -rn "media_example\|db_example_litestar" docs/ src/*/docs/` finds
      no live references to what you deleted.
