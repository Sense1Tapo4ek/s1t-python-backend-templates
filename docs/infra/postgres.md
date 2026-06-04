# infra: PostgreSQL

How Postgres is configured and wired in this template, and the gotchas that
bite. For *why* Postgres replaced SQLite, see [ADR 0019](../adr/0019-sqlite-to-postgres.md).
Audience: contributor / operator.

## Mental model

```
            one Postgres database (litestar_base)
            +-----------------------------------+
  asyncpg ->| schema db_example_sddd  (raw)     |  search_path = db_example_sddd
  alchemy ->| schema db_example_litestar (ORM)  |  search_path = db_example_litestar
            +-----------------------------------+
```

One database, one schema per bounded context. Each connection sets its own
`search_path` to its context schema, so unqualified table names resolve there
and the two contexts never collide. No cross-schema queries.

## Version

Pinned `postgres:18` (compose service `db`). Bump in one place: the compose
`image` tag.

## Driver URLs

`PostgresConfig` (`shared/config.py`, env prefix `POSTGRES_`) derives three
DSNs from the same host/port/user/password/db, one per driver:

| Property | Scheme | Used by |
|:---|:---|:---|
| `asyncpg_dsn` | `postgresql://` | db_example_sddd runtime (raw asyncpg pool + per-request connection) |
| `alchemy_url` | `postgresql+asyncpg://` | db_example_litestar runtime (advanced-alchemy / SQLAlchemy async engine) |
| `yoyo_url` | `postgresql+psycopg://` | db_example_sddd migrations (yoyo, psycopg3 sync backend) |

`db_example_sddd` speaks raw asyncpg for queries and psycopg3 (via yoyo) for
migrations. `db_example_litestar` uses only advanced-alchemy over asyncpg.

## Environment

| Var | Default | Meaning |
|:---|:---|:---|
| `POSTGRES_HOST` | `localhost` | DB host |
| `POSTGRES_PORT` | `5432` | DB port |
| `POSTGRES_USER` | `postgres` | role |
| `POSTGRES_PASSWORD` | `postgres` | password |
| `POSTGRES_DB` | `litestar_base` | database name |
| `DB_EXAMPLE_SDDD_SCHEMA_NAME` | `db_example_sddd` | sddd context schema |
| `DB_EXAMPLE_SDDD_POOL_SIZE` | `4` | asyncpg pool `max_size` |
| `DB_EXAMPLE_LITESTAR_SCHEMA_NAME` | `db_example_litestar` | litestar context schema |

`.env.example` is the contract. No env vars in business logic -- config flows
through Pydantic Settings into Dishka providers.

## Schema isolation via search_path

Each context opens connections with `server_settings={"search_path": <schema>}`:

- asyncpg contexts (sddd, orders): shared `shared/adapters/driven/postgres/`
  (`build_pool`, `open_connection`). Each context builds its OWN pool instance
  (its schema) from the shared builder, so one pool == one search_path holds.
- litestar: `adapters/driven/engine.py` (`build_engine` via `connect_args`).

`search_path` is a connection startup-packet parameter, so it survives asyncpg
pool connection reset/recycle. Unqualified runtime queries are safe.

The shared `SqlUoW` (same package) wraps `conn.transaction()` and is reused by
any asyncpg context; it satisfies each context's `IUoW` Protocol structurally,
so `shared` never imports a bounded context.

## Migrations

| Context | Tool | Where |
|:---|:---|:---|
| db_example_sddd | yoyo (psycopg3 sync backend, run in a thread) | `migrations/db_example_sddd/*.sql`, runner `adapters/driven/migrations_runner.py` |
| db_example_litestar | `create_all` at lifespan startup | none (schema built from ORM metadata) |

The sddd migration DDL is **schema-qualified on purpose**
(`CREATE SCHEMA IF NOT EXISTS ...; CREATE TABLE <schema>.items (...)`): yoyo's
own connection sets its own search_path, so the migration cannot rely on the
runtime one.

## File pointers

- `shared/config.py::PostgresConfig` -- the three DSNs.
- `db_example_sddd/config.py` -- `schema_name`, `pool_size`.
- `shared/adapters/driven/postgres/` -- shared `build_pool` + `open_connection`
  + `SqlUoW`, reused by every asyncpg context.
- `db_example_sddd/ports/driven/pg_item_repo.py` -- raw asyncpg repo.
- `db_example_sddd/adapters/driven/migrations_runner.py` -- yoyo apply.
- `db_example_litestar/adapters/driven/engine.py` -- async engine + sessionmaker.

## Gotchas

- **asyncpg autocommits per statement.** Each `execute`/`fetch` is its own
  transaction. For multi-statement consistency wrap the work:
  `async with conn.transaction(): ...`.
- **Docker required for the local test suite.** Integration and e2e tests spin
  a Postgres testcontainer. No Docker -> point the suite at an external DB via
  `POSTGRES_HOST` (and the other `POSTGRES_*` vars).
- **Do not call `DISCARD ALL` manually.** It would reset `search_path` and
  break unqualified queries; the design relies on the startup-packet value
  surviving pool reset (migration DDL is schema-qualified, runtime queries are
  not).
- **Integration and e2e share one DB/schema.** The integration repo test
  (`test_pg_item_repo.py::test_list_and_delete`) asserts row-count **deltas**
  against a captured baseline, not absolute counts, because the e2e suite
  commits rows into the same schema. Never write absolute-count assertions
  against this schema.

## Pointers

- [ADR 0019](../adr/0019-sqlite-to-postgres.md) -- the decision.
- asyncpg: https://magicstack.github.io/asyncpg/current/
- advanced-alchemy: https://docs.advanced-alchemy.litestar.dev/
- yoyo-migrations: https://ollycope.com/software/yoyo/latest/
- Postgres `search_path`: https://www.postgresql.org/docs/18/ddl-schemas.html#DDL-SCHEMAS-PATH
