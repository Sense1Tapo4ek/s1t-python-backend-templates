# 0015 - db_example_litestar: ORM model lives in domain/
Status: superseded by 0016
Date: 2026-06-02

## Context
ADR 0012 placed the SQLAlchemy models in `adapters/driven/db/`. But the model
is the context's shared entity: driving (DTOs, facade, controllers) and driven
(repos, services) both reference it. From the deepest layer that produced six
downward cross-layer imports, four of them illegal `driving -> adapters/driven`
edges. The model was the most-imported type yet sat at the bottom.

## Decision
Move the ORM models to `domain/orm_models.py` -- the one layer both ports
sides may import. `ports/driving/__init__` re-exports `AuthorModel`/`BookModel`
so controllers (allowed to import only `ports/driving`) get the type for their
`SQLAlchemyDTO` generics. This supersedes the model-placement part of ADR 0012;
its advanced-alchemy, hybrid (no `app/`), and `create_all` decisions stand.

## Consequences
- + Zero `driving -> driven` imports for the model; matches canonical S-DDD
    (the entity is domain).
- + Repos/services/DTOs/facades import the model from `domain/` directly.
- - `domain/` now contains a framework-bound (SQLAlchemy) type, not a pure
    dataclass -- the hybrid trade already accepted in ADR 0012.
- - One side-effect import remains: the lifespan manager imports `domain` for
    `create_all` table registration (`adapters/driven -> domain`).

## Alternatives considered
- `ports/driven/models.py` ("ports level") - keeps the no-domain shape but
  leaves `driving -> driven` model imports for DTOs/facade; rejected.
- Model in `ports/driving` - flips the problem: driven would import driving.
