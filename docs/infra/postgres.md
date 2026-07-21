# infra: PostgreSQL

How Postgres is configured and wired in this template, and the gotchas that
bite. For *why* Postgres replaced SQLite, see [ADR 0019](../adr/0019-sqlite-to-postgres.md).
Audience: contributor / operator.

## Mental model

```
            one Postgres database (litestar_base)
            +-----------------------------------+
  auth  --->| schema auth                       |  search_path = auth
  media --->| schema media                      |  search_path = media
  dbex ---->| schema db_example_litestar        |  search_path = db_example_litestar
            +-----------------------------------+
```

All three contexts speak SQLAlchemy over the asyncpg driver. One database, one
schema per bounded context. The `auth` schema holds `users`, `api_keys`, and
`outbox_messages` (see `migrations/auth/`). Each engine sets its own `search_path` to its
context schema, so unqualified table names resolve there and contexts never
collide. No cross-schema queries.

## Version

Pinned `postgres:18` (compose service `db`). Bump in one place: the compose
`image` tag.

## Driver URLs

`PostgresConfig` (`shared/config.py`, env prefix `POSTGRES_`) derives three
DSNs from the same host/port/user/password/db, one per driver:

| Property | Scheme | Used by |
|:---|:---|:---|
| `alchemy_url` | `postgresql+asyncpg://` | every context's runtime (SQLAlchemy async engine) |
| `yoyo_url` | `postgresql+psycopg://` | `auth` and `media_example` migrations (yoyo, psycopg3 sync backend) |
| `asyncpg_dsn` | `postgresql://` | no runtime user; kept for raw-asyncpg tooling (e.g. the container smoke test) |

All DB contexts run on the SQLAlchemy async engine (`postgresql+asyncpg`).
`auth` and `media_example` use plain SQLAlchemy 2.0; `db_example_litestar` uses
advanced-alchemy. Migrations go through psycopg3 (via yoyo).

## Environment

| Var | Default | Meaning |
|:---|:---|:---|
| `POSTGRES_HOST` | `localhost` | DB host |
| `POSTGRES_PORT` | `5432` | DB port |
| `POSTGRES_USER` | `postgres` | role |
| `POSTGRES_PASSWORD` | `postgres` | password |
| `POSTGRES_DB` | `litestar_base` | database name |
| `DB_EXAMPLE_LITESTAR_SCHEMA_NAME` | `db_example_litestar` | litestar context schema |

Per-context schema/pool knobs (`MEDIA_*`, `AUTH_*`) are documented on the
owning context pages ([media_example](../../src/litestar_backend/docs/contexts/media_example.md),
[auth](../../src/litestar_backend/docs/contexts/auth.md)).

`.env.full.example` is the contract. No env vars in business logic -- config flows
through Pydantic Settings into Dishka providers.

## Schema isolation via search_path

Each context builds its engine with
`connect_args={"server_settings": {"search_path": <schema>}}` via the shared
`build_engine` (`shared/adapters/driven/postgres/engine.py`). Each context owns
its OWN engine instance (its schema), so one engine == one search_path holds.

`search_path` is a connection startup-packet parameter, so it survives
connection-pool reset/recycle. Unqualified runtime queries are safe.

The shared session-based `SqlUoW` (same package) commits or rolls back the
request `AsyncSession` and is reused by any context; it satisfies each
context's `IUoW` Protocol structurally, so `shared` never imports a bounded
context.

## Migrations

| Context | Tool | Where |
|:---|:---|:---|
| auth | yoyo (psycopg3 sync backend, run in a thread) | `migrations/auth/*.sql`, applied by the shared `run_migrations` at lifespan start (first of the managers) |
| media_example | yoyo (same runner) | `migrations/media/*.sql`, applied at lifespan start |
| db_example_litestar | `create_all` at lifespan startup | none (schema built from ORM metadata) |

One shared runner (`shared/adapters/driven/postgres/migrations.py::run_migrations`)
applies any context's folder; each context's lifespan passes its own
`migrations/<context>/`. The media_example migration DDL is **schema-qualified
on purpose**
(`CREATE SCHEMA IF NOT EXISTS ...; CREATE TABLE <schema>.videos (...)`): yoyo's
own connection sets its own search_path, so the migration cannot rely on the
runtime one.

## File pointers

- `shared/config.py::PostgresConfig` -- the three DSNs.
- `media_example/config.py` -- `schema_name`, `pool_size`.
- `shared/adapters/driven/postgres/` -- shared `build_engine`,
  `build_sessionmaker`, `run_migrations`, session `SqlUoW`; reused by every
  context.
- `media_example/ports/driven/sql_video_repo.py` -- SQLAlchemy repo (session,
  `pg_insert` upsert).
- `media_example/ports/driven/orm_models.py` -- `VideoRow` / `OutboxRow`.
- `db_example_litestar/provider.py` -- builds its engine via the shared builder.

## Gotchas

- **One session per request, shared by the repos.** A context's repos and its
  `SqlUoW` take the same REQUEST-scoped `AsyncSession`, so multi-statement work
  (video row + outbox row) commits in one transaction. Resolve the session from
  the request-scoped container, never build a second one.
- **Docker required for the local test suite.** Integration and e2e tests spin
  a Postgres testcontainer. No Docker -> point the suite at an external DB via
  `POSTGRES_HOST` (and the other `POSTGRES_*` vars).
- **Do not call `DISCARD ALL` manually.** It would reset `search_path` and
  break unqualified queries; the design relies on the startup-packet value
  surviving pool reset (migration DDL is schema-qualified, runtime queries are
  not).
- **Integration and e2e share one DB/schema.** media integration tests stay
  isolated by rolling back their session (`test_sql_video_repo.py`) or deleting
  their own rows after a real commit (`test_outbox_relay.py`). The e2e suite
  commits into the same schema, so never write absolute row-count assertions
  against it.

## Pointers

- [ADR 0019](../adr/0019-sqlite-to-postgres.md) -- Postgres over SQLite.
- [ADR 0025](../../src/litestar_backend/docs/adr/0025-standardize-on-sqlalchemy.md) -- single SQLAlchemy stack.
- SQLAlchemy 2.0 async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- asyncpg (driver): https://magicstack.github.io/asyncpg/current/
- advanced-alchemy: https://docs.advanced-alchemy.litestar.dev/
- yoyo-migrations: https://ollycope.com/software/yoyo/latest/
- Postgres `search_path`: https://www.postgresql.org/docs/18/ddl-schemas.html#DDL-SCHEMAS-PATH
