# litestar_backend

The HTTP API service of this monorepo: Litestar 2.24+, strict S-DDD per bounded
context, Dishka DI. Owns Postgres, the admin UI, role-based auth, Prometheus
metrics, and the outbox relay that publishes `video_uploaded`.

A standalone uv project -- own `pyproject.toml`, `uv.lock`, and `Dockerfile`.
Run every command below from this directory.

## Run

```bash
docker compose up --build            # from the repo root: db + this service on :8000
```

Fast inner loop on the host (Docker still required for integration/e2e --
they start a Postgres testcontainer):

```bash
uv sync
uv run start_litestar                # API workers
uv run pytest -m unit                # domain only, instant, no DB
uv run ruff check . && uv run mypy && uv run lint-imports
```

Full gate, canonical form:

```bash
docker compose run --build --rm litestar_backend_test
```

## Where next

- [docs/index.md](docs/index.md) -- this service's contexts, subsystems,
  infrastructure, and ADRs.
- [../../docs/architecture.md](../../docs/architecture.md) -- cross-service
  topology, layer rules, and invariants.
- [../../docs/contract/](../../docs/contract/) -- the wire this service speaks.
- [../../README.md](../../README.md) -- repo overview and first run.
- [../../docs/development.md](../../docs/development.md) -- monorepo tooling,
  Taskfile, pre-commit, CI.
