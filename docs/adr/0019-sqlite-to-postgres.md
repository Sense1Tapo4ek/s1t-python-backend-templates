---
status: accepted
date: 2026-06-03
---
# 0019 - Migrate the template from SQLite to PostgreSQL

## Context
The template shipped on SQLite. It is not representative of a production
backend: no real pooling, no concurrent writers, no native UUID/TIMESTAMPTZ,
no schemas. The two `db_example_*` contexts exist to demonstrate raw-driver
vs ORM persistence, and that contrast is more credible against a real server.

## Decision
Move to Postgres 18, one database, schema-per-context isolated via
`search_path`. `db_example_sddd` uses raw asyncpg for queries and yoyo (psycopg3
sync backend) for migrations. `db_example_litestar` swaps the advanced-alchemy
engine to asyncpg and builds its schema with `create_all`. Tests run against a
Postgres testcontainer, or an external DB when `POSTGRES_HOST` is set.

## Consequences
- + Production-representative: native UUID/TIMESTAMPTZ, real pooling, real
    concurrency.
- + Schema-per-context isolation models multi-context deployments honestly.
- - Docker is now required for the test suite (testcontainers).
- - One more service in docker-compose.

## Alternatives considered
- Keep SQLite -- rejected: unrepresentative of production.
- Single shared schema -- rejected: loses per-context isolation.
- Alembic for sddd -- rejected: yoyo is already in place; the decision keeps it.
