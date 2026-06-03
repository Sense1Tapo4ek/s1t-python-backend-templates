# db_example_sddd context

For contributors learning how to wire raw asyncpg (Postgres) in an S-DDD
context and how Litestar `MsgspecDTO` works with partial PATCH.

This is an **example context** shipped in the template, alongside
`db_example_litestar` and the `metrics` context. Delete them once you have
real contexts.

## Mental model

```
                  PooledItemController        PerRequestItemController
                    /db-example-sddd/pooled/         /db-example-sddd/per-request/
                         |                               |
                   PooledItemFacade             PerRequestItemFacade
                         |                               |
                      ItemFacade (shared logic)
                     /          \
              ItemManagement   ItemQueries
                     \          /
                    IItemRepo (Protocol)
                         |
                     PgItemRepo
                     /          \
            asyncpg pool        open_connection
           (APP-scope, N conns)  (one conn per request)
```

Two variants run simultaneously at different URL prefixes. The domain, app
layer, and repository implementation are identical. Only the connection
source and Dishka scope differ.

## Public surface

### Routes

| Method | Path | Body DTO | Response DTO | Status |
|---|---|---|---|---|
| POST | `/db-example-sddd/pooled/items` | `ItemWriteDTO` | `ItemReadDTO` | 201 |
| GET | `/db-example-sddd/pooled/items` | — | `OffsetPagination[ItemModel]` | 200 |
| GET | `/db-example-sddd/pooled/items/{item_id:uuid}` | — | `ItemReadDTO` | 200 |
| PATCH | `/db-example-sddd/pooled/items/{item_id:uuid}` | `ItemPatchDTO` | `ItemReadDTO` | 200 |
| DELETE | `/db-example-sddd/pooled/items/{item_id:uuid}` | — | — | 204 |
| POST | `/db-example-sddd/per-request/items` | `ItemWriteDTO` | `ItemReadDTO` | 201 |
| GET | `/db-example-sddd/per-request/items` | — | `OffsetPagination[ItemModel]` | 200 |
| GET | `/db-example-sddd/per-request/items/{item_id:uuid}` | — | `ItemReadDTO` | 200 |
| PATCH | `/db-example-sddd/per-request/items/{item_id:uuid}` | `ItemPatchDTO` | `ItemReadDTO` | 200 |
| DELETE | `/db-example-sddd/per-request/items/{item_id:uuid}` | — | — | 204 |

Query params for list: `limit` (default 50), `offset` (default 0).

### ItemModel

`msgspec.Struct` with fields: `id: UUID`, `name: str` (1-200 chars),
`description: str | None`, `created_at: datetime`.

`ItemWriteDTO` excludes `{id, created_at}`.
`ItemPatchDTO` excludes `{id, created_at}`, all fields partial.
PATCH uses `DTOData.as_builtins()` to forward only present keys to the facade.

### Config (`DB_EXAMPLE_SDDD_` prefix)

| Env var | Default | Notes |
|---|---|---|
| `DB_EXAMPLE_SDDD_SCHEMA_NAME` | `db_example_sddd` | Postgres schema this context owns (search_path) |
| `DB_EXAMPLE_SDDD_POOL_SIZE` | `4` | asyncpg pool `max_size` (1-32) |

Postgres connection settings (`POSTGRES_*`) live in shared `PostgresConfig`;
see [docs/infra/postgres.md](../infra/postgres.md).

### Errors

`ItemNotFound(AppError)` -> 404 (registered separately in `api.py` against
`not_found_handler`, overrides the default `AppError` -> 422 mapping).

`EmptyItemName(DomainError)` -> 409.

## The two scope variants

### Pooled (APP-scope pool)

`build_pool` (`adapters/driven/pg_pool.py`) calls `asyncpg.create_pool`
(`min_size=1`, `max_size=pool_size`, `search_path` server setting) at lifespan
start. Each request borrows one connection via `pool.acquire()` (async context
manager); the connection returns to the pool when the request ends. Dishka
provides `PooledItemFacade` at `Scope.REQUEST` using an async generator that
calls `pool.acquire()`.

Use this when you want bounded connection count and connection reuse.

### Per-request (fresh connection)

`PerRequestDbExampleSdddProvider` opens a fresh asyncpg connection per request
via `open_connection(dsn, schema=...)` and closes it in the generator `finally`
block. No pool involved.

Use this to demonstrate the simplest possible wiring, or when
connection-level state isolation matters.

## Migrations

yoyo-migrations applied at lifespan start via `apply_migrations(yoyo_url)`
(yoyo over the `postgresql+psycopg` backend, psycopg3). Migration files live in
`migrations/db_example_sddd/` (parallel to `src/`, `static/`, `docs/`,
`tests/`). Migration table: `_yoyo_migration`. Currently: `001-create-items.sql`
creates the schema and the `items` table; the DDL is schema-qualified on
purpose (yoyo's connection sets its own search_path).

`apply_migrations` runs `yoyo` in `asyncio.to_thread` (yoyo is sync).

## Invariants and gotchas

- Both variants connect to the same Postgres database and schema; isolation
  from `db_example_litestar` is by per-connection `search_path`, not a separate
  store. There is no local DB file and no per-connection setup step. The pooled
  variant shares one asyncpg pool; the per-request variant opens a fresh
  connection each time.
- The asyncpg pool must be created (lifespan start) before any request arrives.
- asyncpg autocommits per statement; wrap multi-statement work in
  `async with conn.transaction(): ...`.
- `PooledItemFacade` and `PerRequestItemFacade` are distinct subclasses of
  `ItemFacade` solely to give Dishka two resolvable types. The implementation
  is inherited and identical.
- Migrations run before the pool is created. Safe to run concurrently across
  workers because yoyo holds a lock for the duration (`backend.lock()`).
- `description` is intentionally nullable (no domain invariant). Setting it
  to `None` in a PATCH does nothing; send `""` if you want to clear it.

## Metrics via ACL (cross-context example)

`ItemManagement.create` emits a counter (`db_example_items_created_total`) and a
histogram (`db_example_item_create_seconds`) to the `metrics` context — the
template's **first ACL example**. The app layer depends on its own
`app/i_metrics.py` (`IMetrics` protocol, duplicated per the S-DDD cross-context
rule); `ports/driven/acl/metrics_acl.py` (`MetricsAcl`) adapts
`metrics.ports.driving.MetricsFacade` to that protocol and is the only place
importing another context. See [docs/contexts/metrics.md](metrics.md).

## Pointers

- `src/db_example_sddd/` — full context source
- `migrations/db_example_sddd/` — yoyo SQL migration files
- [docs/adr/0011-db-example-sddd-pool-vs-per-request.md](../adr/0011-db-example-sddd-pool-vs-per-request.md) — why two variants
- [docs/architecture.md](../architecture.md) — S-DDD layers, DI scopes, lifespan contract
