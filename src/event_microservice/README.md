# event_microservice

The event-driven worker of this monorepo: a FastStream consumer that reads the
`video_uploaded` Valkey Stream, fans heavy work out to SAQ jobs, joins the
results in Valkey, and publishes status events back on `video_status`.

A standalone uv project -- own `pyproject.toml`, `uv.lock`, and `Dockerfile`.
Shares no code with `litestar_backend`; the only coupling is the wire contract.
Run every command below from this directory.

## Run

Two compose services run from this one image: `event_microservice` (the
FastStream consumer) and `event_microservice_worker` (the SAQ worker plus its
monitoring panel).

```bash
# from the repo root
docker compose up event_microservice event_microservice_worker
```

Fast inner loop on the host:

```bash
uv sync
uv run pytest -m unit                   # domain only, instant, no broker
uv run ruff check . && uv run mypy && uv run lint-imports
```

Full gate, canonical form:

```bash
docker compose run --build --rm event_microservice_test
```

## Where next

- [docs/index.md](docs/index.md) -- layout, the `media_processing` context,
  FastStream and SAQ notes, delivery guarantees.
- [../../docs/contract/](../../docs/contract/) -- the two streams this service
  speaks.
- [../../docs/architecture.md](../../docs/architecture.md) -- cross-service
  topology.
- [../../docs/development.md](../../docs/development.md) -- monorepo tooling.
