# db_example_litestar context

For contributors learning how to wire SQLAlchemy 2.0 + advanced-alchemy
under Dishka in an S-DDD context, and how `SQLAlchemyDTO` replaces the
full ports/driving layer.

## Mental model

This context uses **hybrid layering**: no `domain/` or `app/` layers.
advanced-alchemy's `SQLAlchemyAsyncRepositoryService` absorbs both CRUD
orchestration and repository access, leaving ORM models, repo/service
subclasses, a thin facade, DTOs, controllers, and config. The facade in
`ports/driving/` is the context's single public API: HTTP controllers and
in-process callers both reach the CRUD through it.

```
AuthorController                     BookController
 /db-example-litestar/authors          /db-example-litestar/books
          |                                    |
     AuthorFacade                        BookFacade      <- ports/driving
 (public API, also callable from code; REQUEST scope)
          |                                    |
     AuthorService                       BookService
  (SQLAlchemyAsyncRepositoryService)  (SQLAlchemyAsyncRepositoryService)
          |                                    |
     AuthorRepository                   BookRepository
  (SQLAlchemyAsyncRepository)         (SQLAlchemyAsyncRepository)
          |                                    |
     AsyncSession  <--- Dishka REQUEST scope --+
          |
     AsyncEngine  <--- Dishka APP scope
          |
     aiosqlite (SQLite file)
```

`AuthorModel` 1--* `BookModel` via `relationship`. Both models extend
`UUIDAuditBase` which provides `id` (UUID PK), `created_at`, `updated_at`.

## Public surface

### Routes

| Method | Path | Body DTO | Response DTO | Status |
|---|---|---|---|---|
| POST | `/db-example-litestar/authors` | `AuthorWriteDTO` | `AuthorReadDTO` | 201 |
| POST | `/db-example-litestar/authors/bulk` | `list[AuthorModel]` (collection) | `Sequence[AuthorModel]` | 201 |
| GET | `/db-example-litestar/authors` | — | `OffsetPagination[AuthorModel]` | 200 |
| GET | `/db-example-litestar/authors/{author_id:uuid}` | — | `AuthorReadDTO` | 200 |
| PATCH | `/db-example-litestar/authors/{author_id:uuid}` | `AuthorPatchDTO` | `AuthorReadDTO` | 200 |
| DELETE | `/db-example-litestar/authors/{author_id:uuid}` | — | — | 204 |
| POST | `/db-example-litestar/books` | `BookWriteDTO` | `BookReadDTO` | 201 |
| GET | `/db-example-litestar/books` | — | `OffsetPagination[BookModel]` | 200 |

Author list query params: `search` (substring, case-insensitive, on `name`),
`limit` (default 50), `offset` (default 0).

### Facades (`ports/driving/`) — programmatic CRUD

The same CRUD is callable from code without HTTP. Facades are REQUEST-scoped
(they wrap the REQUEST-scoped service) — resolve them from the request-scoped
Dishka container, or construct directly over an `AsyncSession` (see
`tests/integration/db_example_litestar/test_facades.py`).

| Facade | Methods |
|---|---|
| `AuthorFacade` | `create(author)`, `create_many(authors)`, `list(*, search, limit, offset)`, `get(author_id)`, `update(author_id, changes)`, `delete(author_id)` |
| `BookFacade` | `create(book)`, `list(*, limit, offset)` |

Currency is the ORM model: facades accept/return `AuthorModel` / `BookModel`.
`create`/`create_many` take model instances; `update` takes a partial mapping
of changed fields (the controller feeds it `DTOData.as_builtins()`); `get`
eager-loads `books`. All mutating methods `auto_commit`.

### ORM models

`AuthorModel`: `name: str`, `dob: date | None`, `books` (relationship, lazy=noload).
`BookModel`: `title: str`, `author_id: UUID` (FK to `author.id`).

All relationships are `lazy="noload"`. Books are loaded on author `GET /{id}`
only, via `svc.get(id, load=[AuthorModel.books])`.

### DTOs (`ports/driving/`)

All are `SQLAlchemyDTO` subclasses using `SQLAlchemyDTOConfig`.

| DTO | Excluded fields | Partial |
|---|---|---|
| `AuthorReadDTO` | — (max_nested_depth=1) | No |
| `AuthorWriteDTO` | `id`, `created_at`, `updated_at`, `books` | No |
| `AuthorPatchDTO` | `id`, `created_at`, `updated_at`, `books` | Yes |
| `BookReadDTO` | `created_at`, `updated_at`, `author` | No |
| `BookWriteDTO` | `id`, `created_at`, `updated_at`, `author` | No |

Bulk create (`/authors/bulk`) passes a raw `list[AuthorModel]` body without
`DTOData`; advanced-alchemy's `create_many` accepts the model list directly.

### Config (`DB_EXAMPLE_LITESTAR_` prefix)

| Env var | Default | Notes |
|---|---|---|
| `DB_EXAMPLE_LITESTAR_DB_PATH` | `${VOLUME_PATH}/db_example_litestar.db` | Relative paths resolved under `VOLUME_PATH` |

### Errors

`advanced_alchemy.exceptions.NotFoundError` -> 404 (registered against
`not_found_handler` in `api.py`, same handler as `ItemNotFound`).

## Hybrid layering rationale

advanced-alchemy's `SQLAlchemyAsyncRepositoryService` handles filtering
(`SearchFilter`, `LimitOffset`, `OrderBy`), pagination (`get_many_and_count`),
eager-load hints (`load=[...]`), and single-operation auto-commit. Adding
a separate `app/` use-case layer would be a thin pass-through with no
invariants to enforce.

The convention holds: the `ports/driven/` layer still separates repo
(`SQLAlchemyAsyncRepository` subclass) from service
(`SQLAlchemyAsyncRepositoryService` subclass). Controllers import only
`ports/driving/` (facade + DTOs) plus the ORM model for DTO generics. The
facade itself crosses `driving -> driven` (it holds the service) — the one
deliberate relaxation here, so the CRUD has a single public entry point
usable from both HTTP and code (see ADR 0014).

## Schema management

`UUIDAuditBase.metadata.create_all` is called on lifespan start. There are
no migration files for this context — this is deliberate. `create_all` is
appropriate for demo/prototype contexts where schema drift is not a concern.
Production contexts should use yoyo (see `db_example_sddd`) or Alembic.

The ORM models must be imported before `create_all` so they register with
`UUIDAuditBase.metadata`. The lifespan manager imports `orm_models` as a
side-effect immediately before the call.

## SQLAlchemy scope in the template

`db_example_litestar` is the **only** SQLAlchemy user in the template.
`db_example_sddd`, `admin/log`, and all other contexts use aiosqlite directly.
Do not pull SQLAlchemy into other contexts; if needed, write a new context
following this one as a reference.

## Invariants and gotchas

- `auto_commit=True` passed to service mutating methods. Without it the
  session is left open and the transaction never commits.
- `lazy="noload"` on all relationships. Loading books via a list endpoint
  would require explicit `load=` hints, producing N+1 if done per-item.
  Author `GET /{id}` is the intended eager-load call site.
- The `AsyncSession` is REQUEST-scoped. The `AuthorService` and `BookService`
  are also REQUEST-scoped; they share the same session instance within one
  request.
- `create_all` is idempotent on existing tables. It does not apply column
  changes — schema changes require dropping and recreating the file in dev.
- advanced-alchemy's `NamedDependency` API requires Litestar >= 2.23.0.
  The project version floor moved from 2.21 to 2.23 for this reason.

## Pointers

- `src/db_example_litestar/` — full context source
- [docs/adr/0012-db-example-litestar-advanced-alchemy-dishka.md](../adr/0012-db-example-litestar-advanced-alchemy-dishka.md) — advanced-alchemy + hybrid layering + create_all decision
- [docs/adr/0014-db-example-litestar-facade-as-public-api.md](../adr/0014-db-example-litestar-facade-as-public-api.md) — facade as single public API for HTTP + code
- [docs/adr/0013-litestar-2.23-floor.md](../adr/0013-litestar-2.23-floor.md) — version bump rationale
- [docs/contexts/db_example_sddd.md](db_example_sddd.md) — raw aiosqlite counterpart
- [docs/architecture.md](../architecture.md) — S-DDD layers and DI scopes
