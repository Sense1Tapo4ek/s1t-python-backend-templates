# 0012 - db_example_alchemy: advanced-alchemy under Dishka, hybrid layering, create_all
Status: accepted
Date: 2026-06-01

## Context
The db_example_alchemy context demonstrates the SQLAlchemy path.
Three decisions were made together: which ORM helper library to use,
how to layer it under S-DDD, and how to manage schema.

## Decision
Use advanced-alchemy 1.11 (`SQLAlchemyAsyncRepository` +
`SQLAlchemyAsyncRepositoryService`). Adopt hybrid layering: omit `domain/`
and `app/`; put ORM models in `adapters/driven/db/`, repos and services
in `ports/driven/`, DTOs in `ports/driving/`. Apply `create_all` at
lifespan start rather than migration files.

Dishka provides the `AsyncEngine` at APP scope and `AsyncSession` at
REQUEST scope. advanced-alchemy's `create_service_dependencies` is NOT
used; service instances are wired manually in the provider.

## Consequences
- + advanced-alchemy handles filtering, pagination, eager-load hints, and
    auto-commit, eliminating boilerplate use cases for pure CRUD.
- + `SQLAlchemyDTO` replaces hand-written Pydantic schemas.
- + `create_all` is zero-config for a demo context.
- - Hybrid layering deviates from the canonical S-DDD four-layer stack;
    readers must understand the rationale before porting the pattern.
- - `create_all` does not support column-level migrations; production use
    requires Alembic or yoyo.
- - `create_service_dependencies` is intentionally bypassed to keep Dishka
    the single DI source of truth.

## Alternatives considered
- Full S-DDD layers with SQLAlchemy - possible but adds a thin app layer
  with no domain logic, which is noise for a CRUD demo.
- Alembic for migrations - appropriate for production; overkill for a demo
  where the schema rarely changes.
