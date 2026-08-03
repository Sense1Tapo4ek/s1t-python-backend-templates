---
status: accepted
date: 2026-06-08
---
# 0026 - Split the repo into two independent services

## Context
The template needs to demonstrate an event-driven worker (FastStream consumer +
SAQ jobs) alongside the Litestar API. Embedding it as another bounded context in
the single app would couple their dependency graphs, interpreters, and deploy
units, and hide the service boundary the showcase is meant to teach.

## Decision
Restructure into a 2-service monorepo under `src/`: `litestar_backend` (the
existing app) and `event_microservice` (the new worker). Each is a standalone uv
project -- own `pyproject.toml` + `uv.lock`, src-layout, own `Dockerfile`,
own `shared/`. No top-level uv workspace, no shared lockfile, no shared library.
The two share only the `video_uploaded` Valkey-Stream wire contract. Both run via
one root `docker-compose.yml`.

## Consequences
- + True service isolation: independent deps, interpreters, images, deploy units.
- + Either service could be extracted to its own repo unchanged.
- + Src-layout keeps `PROJECT_ROOT` and every `src=["src","tests"]` tool config
    working with no edits; the backend move is nearly pure `git mv`.
- - Infra code (Valkey client, structlog, base errors/config) is duplicated per
    service instead of shared -- accepted as the cost of shared-nothing.
- - Local tool runs (`uv run pytest`, ruff, mypy) move from the repo root into
    each service root.

## Alternatives considered
- Worker as a bounded context in the single app - couples deps/interpreter/deploy;
  defeats the service-boundary showcase; rejected.
- Top-level uv workspace + shared lockfile + shared library - reintroduces the
  coupling the split exists to remove; rejected (see spec discussion).
- Flat package layout per service (no inner `src/`) - shifts `PROJECT_ROOT` up
  one level and breaks `migrations/` / `static/` lookups + tool configs; rejected.
