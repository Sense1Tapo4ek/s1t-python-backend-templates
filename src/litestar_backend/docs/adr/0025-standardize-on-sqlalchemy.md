# 0025 - Standardize the template on SQLAlchemy; retire the raw asyncpg path
Status: accepted
Date: 2026-06-08

## Context
Plan A shipped `media_example` on raw asyncpg (hand-written SQL, manual
Record->domain mapping, a bespoke pool wrapper) alongside `db_example_litestar`
on SQLAlchemy. Two DB stacks doubled the infra surface: two engine/pool
builders, two unit-of-work shapes, two row-mapping styles. ADR 0024 chose media
as the golden context but characterized its data layer as raw asyncpg.

## Decision
One DB stack: SQLAlchemy (driver `postgresql+asyncpg`). `shared` owns the
engine/sessionmaker builder and a session-based `SqlUoW`. `media_example` uses
PLAIN SQLAlchemy 2.0 -- ORM models in `ports/driven`, hand-written repos
implementing the app Protocols, a session-based outbox + relay -- because it
carries domain logic and a transactional outbox. `db_example_litestar` keeps
advanced-alchemy (Repository/Service) for its domain-less CRUD. The raw asyncpg
pool wrapper is deleted.

## Consequences
- + One engine builder, one UoW, one mapping style across the template.
- + The outbox commits atomically with the video row in a single session tx.
- + Teaches both SQLAlchemy idioms: plain 2.0 (media) and advanced-alchemy
    (db_example_litestar).
- - Loses the raw-asyncpg worked example; its SQL/Record mapping lives only in
    git history now.
- - asyncpg stays as the SQLAlchemy driver, so the dependency is unchanged.

## Alternatives considered
- Standardize on raw asyncpg instead - deletes the ORM example and forces
  hand-rolled CRUD everywhere; rejected.
- advanced-alchemy for media too - its auto-commit CRUD model fights the
  same-tx outbox write and the domain state machine; rejected.
