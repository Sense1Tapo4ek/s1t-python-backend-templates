# db_example_litestar context

This is an **example context** shipped in the template (alongside
`media_example`); delete it once you have real contexts.

For contributors learning how to wire SQLAlchemy 2.0 + advanced-alchemy
under Dishka in an S-DDD context, and how `SQLAlchemyDTO` replaces the
full ports/driving layer.

## Mental model

This context uses **hybrid layering**: no `domain/` and no `app/` layer (no
business logic). advanced-alchemy's `SQLAlchemyAsyncRepositoryService` absorbs
both CRUD orchestration and repository access, leaving the ORM model,
repo/service subclasses, a thin facade, DTOs, controllers, and config.

The ORM model is used by **both** sides of ports (driving serialises it, driven
persists it), so it lives at the **`ports/` root** (`ports/orm_models.py`) — not
under `driving/` or `driven/`, which keeps it out of a `driving <-> driven`
crossing. `ports/driving` re-exports it so controllers (which may import only
`ports/driving`) get the type for their `SQLAlchemyDTO` generics. The facade in
`ports/driving/` is the single public API: HTTP controllers and in-process
callers both reach the CRUD through it.

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
     asyncpg (Postgres, schema db_example_litestar)
```

`AuthorModel` 1--* `BookModel` via `relationship`, both in `ports/orm_models.py`
extending `UUIDAuditBase` (`id` UUID PK, `created_at`, `updated_at`). DTOs,
facades (driving) and repos, services (driven) all import them from
`ports/orm_models`.

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

### ORM models (`ports/orm_models.py`)

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
| `DB_EXAMPLE_LITESTAR_SCHEMA_NAME` | `db_example_litestar` | Postgres schema this context owns (search_path) |

Postgres connection settings (`POSTGRES_*`) live in shared `PostgresConfig`;
see [docs/infra/postgres.md](../../../../docs/infra/postgres.md).

### Errors

`advanced_alchemy.exceptions.NotFoundError` -> 404 (registered against
`not_found_to_problem` in `root/composition/app.py`, the same handler as the
app-layer `NotFoundError`).

## Hybrid layering rationale

advanced-alchemy's `SQLAlchemyAsyncRepositoryService` handles filtering
(`SearchFilter`, `LimitOffset`, `OrderBy`), pagination (`get_many_and_count`),
eager-load hints (`load=[...]`), and single-operation auto-commit. Adding
a separate `app/` use-case layer would be a thin pass-through with no
invariants to enforce.

The convention holds: the `ports/driven/` layer still separates repo
(`SQLAlchemyAsyncRepository` subclass) from service
(`SQLAlchemyAsyncRepositoryService` subclass). The ORM model lives at the
`ports/` root (used by both branches), so both ports sides import it without
crossing `driving <-> driven`; controllers reach it via the `ports/driving`
re-export (they may import only `ports/driving`). See ADR 0016 for the model
placement (supersedes ADR 0015).

Remaining deliberate relaxations, both narrow and documented:
- the facade holds the service (`driving -> driven`) so the CRUD has a single
  public entry point usable from HTTP and code (ADR 0014);
- the lifespan manager (at `adapters/`) imports `ports.orm_models` once for
  `create_all` table registration — a pure side-effect import;
- the model is a SQLAlchemy ORM type rather than a framework-free dataclass —
  acceptable because the context has no business logic (ADR 0012).

## Schema management

`UUIDAuditBase.metadata.create_all` is called on lifespan start, after the
context's Postgres schema is created (`build_engine(alchemy_url, schema)` sets
`search_path`, so tables land in `db_example_litestar`). There are no migration
files for this context — this is deliberate. `create_all` is appropriate for
demo/prototype contexts where schema drift is not a concern. Production contexts
should use yoyo (see `media_example`) or Alembic.

The ORM models must be imported before `create_all` so they register with
`UUIDAuditBase.metadata`. The lifespan manager
(`adapters/lifespan_manager.py`) imports `ports.orm_models`
at module level for that side effect.

## advanced-alchemy scope in the template

`db_example_litestar` is the **only** advanced-alchemy user. Both DB contexts
run on SQLAlchemy (`postgresql+asyncpg`): `media_example` uses plain
SQLAlchemy 2.0 (it has domain logic + a transactional outbox), this context
uses advanced-alchemy's Repository/Service for domain-less CRUD. `admin/log`
reads JSONL log files and touches no DB. Reach for advanced-alchemy when a
context is thin CRUD; reach for plain SQLAlchemy when it has real domain logic.
See ADR 0025.

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
  changes — schema changes require dropping and recreating the tables in dev.
- advanced-alchemy's `NamedDependency` API requires Litestar >= 2.23.0.
  The floor moved from 2.21 to 2.23 for this reason (ADR 0013) and has since
  moved to >= 2.24.0 (`pyproject.toml` is authoritative).

## Pointers

- `src/db_example_litestar/` — full context source
- [docs/adr/0012-db-example-litestar-advanced-alchemy-dishka.md](db_example_litestar/adr/0012-db-example-litestar-advanced-alchemy-dishka.md) — advanced-alchemy + hybrid layering + create_all decision
- [docs/adr/0014-db-example-litestar-facade-as-public-api.md](db_example_litestar/adr/0014-db-example-litestar-facade-as-public-api.md) — facade as single public API for HTTP + code
- [docs/adr/0016-db-example-litestar-orm-model-in-ports-root.md](db_example_litestar/adr/0016-db-example-litestar-orm-model-in-ports-root.md) — ORM model at `ports/` root (used by both branches); supersedes 0015
- [docs/adr/0015-db-example-litestar-orm-model-in-domain.md](db_example_litestar/adr/0015-db-example-litestar-orm-model-in-domain.md) — (superseded by 0016) ORM model in domain/
- [docs/adr/0013-litestar-2.23-floor.md](../adr/0013-litestar-2.23-floor.md) — version bump rationale (the floor has since moved to 2.24)
- [docs/contexts/media_example.md](media_example.md) — plain-SQLAlchemy counterpart (golden context)
- [docs/infra/postgres.md](../../../../docs/infra/postgres.md) — Postgres wiring (schemas, DSNs, search_path)
- [docs/architecture.md](../../../../docs/architecture.md) — S-DDD layers and DI scopes
