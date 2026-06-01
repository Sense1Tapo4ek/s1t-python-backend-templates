# db_example context

For contributors learning how to wire aiosqlite in an S-DDD context and
how Litestar `MsgspecDTO` works with partial PATCH.

## Mental model

```
                  PooledItemController        PerRequestItemController
                    /db-example/pooled/         /db-example/per-request/
                         |                               |
                   PooledItemFacade             PerRequestItemFacade
                         |                               |
                      ItemFacade (shared logic)
                     /          \
              ItemManagement   ItemQueries
                     \          /
                    IItemRepo (Protocol)
                         |
                   SqliteItemRepo
                     /          \
              SqlitePool        open_connection
           (APP-scope, N conns)  (one conn per request)
```

Two variants run simultaneously at different URL prefixes. The domain, app
layer, and repository implementation are identical. Only the connection
source and Dishka scope differ.

## Public surface

### Routes

| Method | Path | Body DTO | Response DTO | Status |
|---|---|---|---|---|
| POST | `/db-example/pooled/items` | `ItemWriteDTO` | `ItemReadDTO` | 201 |
| GET | `/db-example/pooled/items` | — | `OffsetPagination[ItemModel]` | 200 |
| GET | `/db-example/pooled/items/{item_id:uuid}` | — | `ItemReadDTO` | 200 |
| PATCH | `/db-example/pooled/items/{item_id:uuid}` | `ItemPatchDTO` | `ItemReadDTO` | 200 |
| DELETE | `/db-example/pooled/items/{item_id:uuid}` | — | — | 204 |
| POST | `/db-example/per-request/items` | `ItemWriteDTO` | `ItemReadDTO` | 201 |
| GET | `/db-example/per-request/items` | — | `OffsetPagination[ItemModel]` | 200 |
| GET | `/db-example/per-request/items/{item_id:uuid}` | — | `ItemReadDTO` | 200 |
| PATCH | `/db-example/per-request/items/{item_id:uuid}` | `ItemPatchDTO` | `ItemReadDTO` | 200 |
| DELETE | `/db-example/per-request/items/{item_id:uuid}` | — | — | 204 |

Query params for list: `limit` (default 50), `offset` (default 0).

### ItemModel

`msgspec.Struct` with fields: `id: UUID`, `name: str` (1-200 chars),
`description: str | None`, `created_at: datetime`.

`ItemWriteDTO` excludes `{id, created_at}`.
`ItemPatchDTO` excludes `{id, created_at}`, all fields partial.
PATCH uses `DTOData.as_builtins()` to forward only present keys to the facade.

### Config (`DB_EXAMPLE_` prefix)

| Env var | Default | Notes |
|---|---|---|
| `DB_EXAMPLE_DB_PATH` | `${VOLUME_PATH}/db_example.db` | Relative paths resolved under `VOLUME_PATH` |
| `DB_EXAMPLE_POOL_SIZE` | `4` | Pool-variant connection count (1-32) |

### Errors

`ItemNotFound(AppError)` -> 404 (registered separately in `api.py` against
`not_found_handler`, overrides the default `AppError` -> 422 mapping).

`EmptyItemName(DomainError)` -> 409.

## The two scope variants

### Pooled (APP-scope pool)

`SqlitePool` opens `pool_size` aiosqlite connections at lifespan start and
parks them in an `asyncio.Queue`. Each request borrows one connection via
`pool.acquire()` (async context manager); the connection returns to the
queue when the request ends. Dishka provides `PooledItemFacade` at
`Scope.REQUEST` using an async generator that calls `pool.acquire()`.

Use this when you want bounded connection count, connection reuse, and
WAL-mode benefits.

### Per-request (fresh connection)

`PerRequestDbExampleProvider` opens a fresh `aiosqlite` connection per
request via `open_connection(db_path)` and closes it in the generator
`finally` block. No pool involved.

Use this to demonstrate the simplest possible wiring, or when
connection-level state isolation matters.

## Migrations

yoyo-migrations applied at lifespan start via `apply_migrations(db_path)`.
Migration files live in `migrations/db_example/` (parallel to `src/`,
`static/`, `docs/`, `tests/`). Migration table: `_yoyo_migration`.
Currently: `001-create-items.sql` creates the `item` table.

`apply_migrations` runs `yoyo` in `asyncio.to_thread` (yoyo is sync).

## Invariants and gotchas

- Both variants share one SQLite file. WAL mode is enabled by `configure(conn)`
  so concurrent reads from the pool do not block writes.
- `SqlitePool` must be opened (lifespan start) before any request arrives.
  Calling `acquire()` on a closed pool raises `RuntimeError`.
- `PooledItemFacade` and `PerRequestItemFacade` are distinct subclasses of
  `ItemFacade` solely to give Dishka two resolvable types. The implementation
  is inherited and identical.
- Migrations run before `pool.open()`. Safe to run concurrently across
  workers because yoyo acquires a file lock.
- `description` is intentionally nullable (no domain invariant). Setting it
  to `None` in a PATCH does nothing; send `""` if you want to clear it.

## Pointers

- `src/db_example/` — full context source
- `migrations/db_example/` — yoyo SQL migration files
- [docs/adr/0011-db-example-pool-vs-per-request.md](../adr/0011-db-example-pool-vs-per-request.md) — why two variants
- [docs/architecture.md](../architecture.md) — S-DDD layers, DI scopes, lifespan contract
