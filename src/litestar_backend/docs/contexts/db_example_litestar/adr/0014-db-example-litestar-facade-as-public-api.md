# 0014 - db_example_litestar: facade as the context's single public API
Status: accepted
Date: 2026-06-01

## Context
The hybrid layering of db_example_litestar (ADR 0012) initially let HTTP
controllers call the advanced-alchemy service directly. That left the CRUD
reachable only over HTTP — in-process callers had no entry point — and gave
the context no public surface analogous to other contexts' facades.

## Decision
Add `AuthorFacade` and `BookFacade` in `ports/driving/`, REQUEST-scoped,
wrapping the respective service. They speak the ORM model as currency and
expose CRUD + list/search. Controllers route through the facade instead of
the service; in-process callers resolve the facade from the request-scoped
container (or construct it over an `AsyncSession`). The facade is the single
public API for both HTTP and code.

## Consequences
- + One CRUD entry point; the same operations work from HTTP and from code.
- + Controllers import only `ports/driving/` (plus the ORM model for DTO
    generics), restoring the layer boundary the service-direct call broke.
- - The facade crosses `driving -> driven` (it holds the service) — a
    deliberate relaxation, documented, not to be copied into a strict context.

## Alternatives considered
- Keep controllers on the service, add facade as a separate code-only path -
  two divergent routes to the same CRUD; rejected as redundant.
- Return DTOs from the facade instead of ORM models - the controller's
  `return_dto` already serialises models; an extra mapping adds noise.
